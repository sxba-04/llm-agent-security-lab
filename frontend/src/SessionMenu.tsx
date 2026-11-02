import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { UserRound, X } from 'lucide-react';
import { api, confirmDiscardChanges, message, sessionIdentity, signOut, subscribeSession, useResource } from './api';
import type { OperatorSession } from './types';

export function SessionMenu() {
  const user = useSyncExternalStore(subscribeSession, sessionIdentity);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const menu = useRef<HTMLDivElement>(null);
  const sessions = useResource<{ sessions: OperatorSession[] }>(open && user ? '/api/auth/sessions' : null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (!menu.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('click', close);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', escape); };
  }, [open]);
  if (!user) return null;
  async function revoke(session: OperatorSession) {
    if (session.current) { if (confirmDiscardChanges()) void signOut(); return; }
    setBusy(session.id); setError('');
    try { await api(`/api/auth/sessions/${encodeURIComponent(session.id)}`, { method: 'DELETE' }); sessions.refresh(); }
    catch (err) { setError(message(err)); }
    finally { setBusy(''); }
  }
  return <div className="session-menu" ref={menu}>
    <button className="button quiet small session-account" type="button" aria-expanded={open} aria-controls="operator-sessions" onClick={() => setOpen(value => !value)} title={`GitHub-Konto @${user.login}`}><UserRound size={15} /><span>@{user.login}</span></button>
    {open && <section className="session-panel" id="operator-sessions" aria-label="Deine Sitzungen">
      <div className="session-panel-heading"><h2>Deine Sitzungen</h2><button className="icon-button" type="button" aria-label="Sitzungen schließen" onClick={() => setOpen(false)}><X size={18} /></button></div>
      <p>Angemeldet als <strong>@{user.login}</strong> · Projektmitglied</p>
      <p>Du kannst gemeinsame Versuchsdaten lesen und bearbeiten. Hier verwaltest du ausschließlich deine eigenen GitHub-Sitzungen.</p>
      {(error || sessions.error) && <p className="notice error" role="alert">{error || sessions.error}</p>}
      {sessions.loading && <p role="status">Sitzungen werden geladen …</p>}
      {sessions.data && <ul className="session-list">{sessions.data.sessions.map(session => <li key={session.id}><div><strong>{session.current ? 'Diese Sitzung' : 'Weitere Sitzung'}</strong><span>Beginn: {sessionDate(session.created_at)}</span><span>Ende: {sessionDate(session.expires_at)}</span></div><button className="button secondary small" type="button" disabled={Boolean(busy)} onClick={() => { void revoke(session); }}>{session.current ? 'Hier abmelden' : 'Beenden'}</button></li>)}</ul>}
      <button className="text-button" type="button" onClick={sessions.refresh} disabled={sessions.loading}>Liste aktualisieren</button>
      <p className="muted">Nach einem Serverneustart ist eine neue Anmeldung nötig. Deine gespeicherten Versuchsdaten sind davon unabhängig.</p>
    </section>}
  </div>;
}
function sessionDate(value: string) { return new Date(value).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' }); }
