import { useEffect, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { ArrowRight, LogIn, LockKeyhole, ShieldCheck } from 'lucide-react';
import { hosted, message, publicAuthRequest, sessionIsAuthenticated, sessionMessage, signIn, subscribeSession } from './api';
import { finishGitHubReturn, startGitHubLogin } from './github-auth';

export function AccessGate({ children }: Readonly<{ children: ReactNode }>) {
  const connected = useSyncExternalStore(subscribeSession, sessionIsAuthenticated);
  const notice = useSyncExternalStore(subscribeSession, sessionMessage);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [githubEnabled, setGithubEnabled] = useState(false);
  const [optionsError, setOptionsError] = useState('');
  const [optionsRevision, setOptionsRevision] = useState(0);
  useEffect(() => {
    if (!hosted || connected) return;
    let active = true;
    const callback = finishGitHubReturn();
    if (callback) {
      setBusy(true);
      void callback.catch(err => { if (active) setError(message(err)); }).finally(() => { if (active) setBusy(false); });
    }
    setOptionsError('');
    void publicAuthRequest<{ github_enabled: boolean }>('/api/auth/config')
      .then(config => { if (active) setGithubEnabled(config.github_enabled === true); })
      .catch(() => { if (active) setOptionsError('Die GitHub-Anmeldeoption ist gerade nicht erreichbar. Dein Zugangscode bleibt verfügbar.'); });
    return () => { active = false; };
  }, [connected, optionsRevision]);
  if (!hosted || connected) return children;
  async function login() {
    setError(''); setBusy(true);
    try { await signIn(code); setCode(''); }
    catch (err) { setError(message(err)); }
    finally { setBusy(false); }
  }
  async function githubLogin() {
    setError(''); setBusy(true);
    try { window.location.assign(await startGitHubLogin()); }
    catch (err) { setError(message(err)); setBusy(false); }
  }
  return <main className="access-page">
    <section className="access-card" aria-labelledby="access-title">
      <div className="access-brand"><span className="brand-mark"><ShieldCheck size={27} /></span><span>Agent Security Lab<small>GEMEINSAME FORSCHUNGSWERKBANK</small></span></div>
      <span className="access-icon"><LockKeyhole size={25} /></span>
      <p className="eyebrow">GESCHÜTZTER ARBEITSBEREICH</p>
      <h1 id="access-title">Willkommen im Labor.</h1>
      <p>Melde dich an, um die gemeinsamen Versuche, PDF-Quellen und Bewertungen zu öffnen.</p>
      {githubEnabled && <div className="github-login"><button className="button primary full-width" type="button" onClick={() => { void githubLogin(); }} disabled={busy}><LogIn size={18} />{busy ? 'Anmeldung wird geprüft …' : 'Mit GitHub anmelden'}</button><p className="muted small-text">Nur die freigegebenen GitHub-Konten des Projektteams erhalten Zugang.</p><div className="access-divider">oder mit Zugangscode</div></div>}
      {optionsError && <div className="small-text muted" role="status">{optionsError} <button className="text-button" type="button" onClick={() => setOptionsRevision(value => value + 1)}>Erneut prüfen</button></div>}
      <form onSubmit={event => { event.preventDefault(); void login(); }}>
        <label className="field"><span>Zugangscode</span><input type="password" autoComplete="off" spellCheck={false} autoCapitalize="none" value={code} onChange={event => setCode(event.target.value)} disabled={busy} required aria-describedby="access-help" /></label>
        <p id="access-help" className="muted small-text">Verwende deinen Labor-Zugangscode. Ein Modell-API-Schlüssel wird hier nicht benötigt.</p>
        {(error || notice) && <p className="notice error" role="alert">{error || notice}</p>}
        <button className="button primary" type="submit" disabled={!code.trim() || busy}>{busy ? 'Verbindung wird geprüft …' : 'Werkbank öffnen'}<ArrowRight size={17} /></button>
      </form>
      <div className="access-note"><ShieldCheck size={18} /><span>Deine Werkbank-Sitzung bleibt im Arbeitsspeicher. Nach dem Neuladen meldest du dich erneut an. GitHub-Sitzungen enden spätestens nach acht Stunden und lassen sich unter „Deine Sitzungen“ beenden.</span></div>
      <details className="muted small-text"><summary>Zugangscode verloren oder Anmeldung fehlgeschlagen?</summary><p>Prüfe zuerst deinen Passwortmanager und kopiere den vollständigen Code. Ein verlorener Code kann nicht wiederhergestellt werden; der Betreiber kann einen neuen ausstellen und den alten sperren.</p><p>Ein Verbindungsfehler bedeutet nicht, dass dein Code falsch ist. Warte kurz und versuche es erneut. Ein Serverneustart allein ändert deinen Zugangscode nicht.</p></details>
      <footer>Synthetische Daten · Kontrollierte Mock-Versuche</footer>
    </section>
  </main>;
}
