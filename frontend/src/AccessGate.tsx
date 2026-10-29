import { useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react';
import { hosted, message, sessionIsAuthenticated, signIn, subscribeSession } from './api';

export function AccessGate({ children }: { children: ReactNode }) {
  const connected = useSyncExternalStore(subscribeSession, sessionIsAuthenticated);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  if (!hosted || connected) return children;
  async function login() {
    setError(''); setBusy(true);
    try { await signIn(code); setCode(''); }
    catch (err) { setError(message(err)); }
    finally { setBusy(false); }
  }
  return <main className="access-page">
    <section className="access-card" aria-labelledby="access-title">
      <div className="access-brand"><span className="brand-mark"><ShieldCheck size={27} /></span><span>Agent Security Lab<small>GEMEINSAME FORSCHUNGSWERKBANK</small></span></div>
      <span className="access-icon"><LockKeyhole size={25} /></span>
      <p className="eyebrow">GESCHÜTZTER ARBEITSBEREICH</p>
      <h1 id="access-title">Willkommen im Labor.</h1>
      <p>Mit deinem persönlichen Zugangscode öffnest du die gemeinsamen Versuche, PDF-Quellen und Bewertungen.</p>
      <form onSubmit={event => { event.preventDefault(); void login(); }}>
        <label className="field"><span>Zugangscode</span><input type="password" autoComplete="off" spellCheck={false} autoCapitalize="none" value={code} onChange={event => setCode(event.target.value)} disabled={busy} required aria-describedby="access-help" /></label>
        <p id="access-help" className="muted small-text">Verwende deinen Labor-Zugangscode. Ein Modell-API-Schlüssel wird hier nicht benötigt.</p>
        {error && <p className="notice error" role="alert">{error}</p>}
        <button className="button primary" type="submit" disabled={!code.trim() || busy}>{busy ? 'Verbindung wird geprüft …' : 'Werkbank öffnen'}<ArrowRight size={17} /></button>
      </form>
      <div className="access-note"><ShieldCheck size={18} /><span>Der Zugangscode bleibt nur für diese Sitzung im Arbeitsspeicher. Nach dem Neuladen meldest du dich erneut an.</span></div>
      <footer>Synthetische Daten · Kontrollierte Mock-Versuche</footer>
    </section>
  </main>;
}
