import { ApiError, publicAuthRequest, sessionGeneration, signInWithGitHubSession } from './api';

const pendingKey = 'security-lab-github-pkce';
const loginLifetime = 600_000;
interface PendingLogin { verifier: string; state: string; expiresAt: number }
interface LoginStart { authorization_url: string; state: string; expires_in: number }
let callbackCompletion: Promise<boolean> | undefined;

function base64url(bytes: Uint8Array) {
  return btoa(String.fromCodePoint(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
}
function forgetPendingLogin() {
  try { window.sessionStorage.removeItem(pendingKey); } catch { /* Storage can be disabled by browser policy. */ }
}
export async function startGitHubLogin() {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
  const start = await publicAuthRequest<LoginStart>('/api/auth/github/start', { code_challenge: challenge });
  const target = authorizationTarget(start, challenge);
  try {
    window.sessionStorage.setItem(pendingKey, JSON.stringify({ verifier, state: start.state, expiresAt: Date.now() + start.expires_in * 1000 }));
  } catch {
    throw new ApiError('Der Browser blockiert den temporären Anmeldespeicher. Erlaube Sitzungsspeicher für diese Seite oder verwende deinen Zugangscode.', 0);
  }
  return target;
}
function authorizationTarget(start: LoginStart, challenge: string) {
  let target: URL;
  try { target = new URL(start.authorization_url); } catch { throw new ApiError('Die GitHub-Anmeldung ist nicht korrekt konfiguriert.', 0); }
  const redirect = `${window.location.origin}${window.location.pathname}`;
  const parameterNames = [...target.searchParams.keys()];
  if (target.origin !== 'https://github.com' || target.pathname !== '/login/oauth/authorize' || target.username || target.password || target.hash
    || new Set(parameterNames).size !== parameterNames.length
    || typeof start.state !== 'string' || !/^[A-Za-z0-9_-]{32,128}$/.test(start.state)
    || !Number.isInteger(start.expires_in) || start.expires_in < 1 || start.expires_in > loginLifetime / 1000
    || target.searchParams.get('state') !== start.state || target.searchParams.get('code_challenge') !== challenge
    || target.searchParams.get('code_challenge_method') !== 'S256' || target.searchParams.get('redirect_uri') !== redirect) {
    throw new ApiError('Die GitHub-Anmeldung ist nicht korrekt konfiguriert.', 0);
  }
  // Build the navigation origin/path from a constant after validating the
  // response and the browser-bound OAuth parameters, never from API text.
  const destination = new URL('https://github.com/login/oauth/authorize');
  destination.search = target.search;
  return destination.href;
}
function pendingLogin(): PendingLogin {
  let value: PendingLogin;
  try { value = JSON.parse(window.sessionStorage.getItem(pendingKey) || 'null') as PendingLogin; }
  catch { throw new ApiError('Die GitHub-Anmeldung gehört nicht zu dieser Browsersitzung. Bitte erneut starten.', 401); }
  finally { forgetPendingLogin(); }
  if (!value || typeof value.verifier !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(value.verifier)
    || typeof value.state !== 'string' || !/^[A-Za-z0-9_-]{32,128}$/.test(value.state)) {
    throw new ApiError('Die GitHub-Anmeldung gehört nicht zu dieser Browsersitzung. Bitte erneut starten.', 401);
  }
  if (!Number.isFinite(value.expiresAt) || value.expiresAt <= Date.now() || value.expiresAt > Date.now() + loginLifetime) {
    throw new ApiError('Die GitHub-Anmeldung ist abgelaufen. Bitte erneut starten.', 401);
  }
  return value;
}
async function completeReturn(query: URLSearchParams, generation: number) {
  const pending = pendingLogin();
  if (query.getAll('state').length !== 1 || query.get('state') !== pending.state) {
    throw new ApiError('Die GitHub-Anmeldung konnte dieser Browsersitzung nicht zugeordnet werden. Bitte erneut starten.', 401);
  }
  if (query.has('error')) throw new ApiError('Die Anmeldung bei GitHub wurde abgebrochen oder nicht freigegeben. Bitte erneut versuchen.', 401);
  const code = query.get('code');
  if (query.getAll('code').length !== 1 || !code || code.length > 512) throw new ApiError('Die GitHub-Antwort ist unvollständig. Bitte erneut anmelden.', 401);
  const result = await publicAuthRequest<{ access_token: string }>('/api/auth/github/complete', { code, state: pending.state, code_verifier: pending.verifier });
  await signInWithGitHubSession(result.access_token, generation);
  return true;
}
export function finishGitHubReturn(): Promise<boolean> | null {
  // StrictMode can mount the gate twice. Consume each callback exactly once.
  if (callbackCompletion) return callbackCompletion;
  const url = new URL(window.location.href);
  if (!url.searchParams.has('code') && !url.searchParams.has('error') && !url.searchParams.has('state')) return null;
  const query = new URLSearchParams(url.search);
  for (const name of ['code', 'state', 'error', 'error_description', 'error_uri']) url.searchParams.delete(name);
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
  callbackCompletion = completeReturn(query, sessionGeneration()).then(
    result => { callbackCompletion = undefined; return result; },
    error => { callbackCompletion = undefined; throw error; },
  );
  return callbackCompletion;
}
