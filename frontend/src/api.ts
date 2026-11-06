import { useCallback, useEffect, useRef, useState } from 'react';
import type { Health, SessionUser } from './types';

export const hosted = import.meta.env.VITE_HOSTED === 'true';
const apiBase = hosted ? import.meta.env.VITE_API_BASE_URL : '';
let csrfToken = '';
let accessToken = '';
let authenticated = false;
let sessionRevision = 0;
let sessionNotice = '';
let sessionUser: SessionUser | null = null;
let authenticationMethod: 'access-code' | 'github' = 'access-code';
const sessionListeners = new Set<() => void>();
export const subscribeSession = (listener: () => void) => { sessionListeners.add(listener); return () => { sessionListeners.delete(listener); }; };
export const sessionIsAuthenticated = () => authenticated;
export const sessionMessage = () => sessionNotice;
export const sessionIdentity = () => sessionUser;
export const sessionGeneration = () => sessionRevision;
function notifySession() { for (const listener of sessionListeners) listener(); }
function clearSession(notice = '') {
  sessionRevision += 1;
  accessToken = ''; csrfToken = ''; authenticated = false; sessionUser = null; sessionNotice = notice; notifySession();
}
export async function signOut() {
  const token = accessToken;
  const csrf = csrfToken;
  const revoke = authenticationMethod === 'github' && Boolean(token);
  clearSession();
  authenticationMethod = 'access-code';
  const revision = sessionRevision;
  if (!revoke) return;
  try {
    const response = await fetchResponse('/api/auth/logout', { method: 'POST' }, requestHeaders({}, true, token, csrf));
    if (!response.ok && response.status !== 401) throw new ApiError('Abmeldung fehlgeschlagen.', response.status);
  } catch {
    if (revision === sessionRevision) {
      sessionNotice = 'Du bist auf diesem Gerät abgemeldet. Der Server konnte die Sitzung nicht bestätigen; sie läuft spätestens nach acht Stunden ab. Du kannst sie nach erneuter Anmeldung unter „Deine Sitzungen“ beenden.';
      notifySession();
    }
  }
}
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function signIn(value: string) {
  const candidate = value.trim();
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(candidate)) throw new ApiError('Bitte den vollständigen Zugangscode eingeben.', 401);
  return establishSession(candidate, 'access-code');
}
export async function signInWithGitHubSession(token: string, expectedGeneration: number) {
  if (sessionRevision !== expectedGeneration) throw new ApiError('Die Anmeldung wurde beendet. Bitte erneut anmelden.', 401);
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(token)) throw new ApiError('Der Server liefert keine gültige GitHub-Sitzung.', 0);
  return establishSession(token, 'github');
}
async function establishSession(candidate: string, method: 'access-code' | 'github') {
  const attempt = ++sessionRevision;
  accessToken = candidate; csrfToken = ''; authenticated = false; sessionNotice = ''; sessionUser = null; authenticationMethod = method; notifySession();
  try {
    const health = await api<Health>('/api/health');
    if (typeof health.csrf_token !== 'string' || !health.csrf_token) throw new ApiError('Der Server liefert keine gültige Werkbank-Sitzung.', 0);
    if (sessionRevision !== attempt) throw new ApiError('Die Anmeldung wurde beendet. Bitte erneut anmelden.', 401);
    if (method === 'github' && !validSessionUser(health.user)) throw new ApiError('Der Server liefert keine gültige GitHub-Identität.', 0);
    sessionUser = method === 'github' ? health.user! : null;
    authenticated = true; notifySession();
  } catch (error) {
    if (sessionRevision === attempt) {
      void signOut();
    }
    throw error;
  }
}
function validSessionUser(value: unknown): value is SessionUser {
  if (!value || typeof value !== 'object') return false;
  const user = value as SessionUser;
  return Number.isSafeInteger(user.id) && user.id > 0 && typeof user.login === 'string' && /^[A-Za-z0-9-]{1,39}$/.test(user.login)
    && user.role === 'researcher' && Array.isArray(user.permissions) && user.permissions.every(permission => typeof permission === 'string');
}
function endpoint(path: string) {
  // Only application paths may receive the private authorization header.
  if (!path.startsWith('/api/') || !new URL(path, 'https://local.invalid').pathname.startsWith('/api/')) {
    throw new ApiError('Ungültiger API-Pfad.', 0);
  }
  return `${apiBase || ''}${path}`;
}
function requestHeaders(options: RequestInit, mutating: boolean, requestToken: string, requestCsrf: string) {
  const headers = new Headers(options.headers);
  if (hosted) {
    if (!requestToken) throw new ApiError('Bitte zuerst anmelden.', 401);
    headers.set('Authorization', `Bearer ${requestToken}`);
  }
  if (mutating) headers.set('X-Lab-Token', requestCsrf);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  return headers;
}
async function fetchResponse(path: string, options: RequestInit, headers: Headers) {
  try { return await fetch(endpoint(path), { ...options, headers, credentials: hosted ? 'omit' : 'same-origin', redirect: 'error' }); }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(hosted ? 'Die Online-Werkbank ist nicht erreichbar. Bitte Verbindung und Serverstatus prüfen.' : 'Die lokale Werkbank ist nicht erreichbar. Prüfe, ob der Python-Prozess noch läuft.', 0);
  }
}
export async function publicAuthRequest<T>(path: '/api/auth/config' | '/api/auth/github/start' | '/api/auth/github/complete', body?: unknown): Promise<T> {
  const options: RequestInit = body === undefined ? {} : { method: 'POST', body: JSON.stringify(body) };
  const headers = new Headers(body === undefined ? undefined : { 'Content-Type': 'application/json' });
  const response = await fetchResponse(path, { ...options, cache: 'no-store' }, headers);
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(responseErrorMessage(result.detail, response.status), response.status);
  return result as T;
}
function responseErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.slice(1).join('.') || 'Eingabe'}: ${item.msg || 'ungültig'}`).join(' · ');
  }
  return `Die Anfrage konnte nicht verarbeitet werden (${status}).`;
}
async function rejectResponse(response: Response, mutating: boolean, requestSession: number, requestCsrf: string): Promise<never> {
  if (hosted && response.status === 401 && sessionRevision === requestSession) {
    clearSession(authenticationMethod === 'github'
      ? 'Deine GitHub-Sitzung ist abgelaufen oder wurde beendet. Bitte erneut mit GitHub anmelden.'
      : 'Der Server akzeptiert deinen Zugangscode nicht mehr. Bitte erneut anmelden oder einen neuen Code beim Betreiber anfordern.');
  }
  const body = await response.json().catch(() => ({}));
  if (mutating && response.status === 403 && body.code === 'csrf_token_invalid') {
    if (sessionRevision === requestSession && csrfToken === requestCsrf) csrfToken = '';
    // Never replay a write automatically, even when middleware rejected it.
    throw new ApiError('Die Serversitzung wurde erneuert. Die Aktion wurde nicht ausgeführt. Bitte die Aktion erneut ausführen.', 403);
  }
  throw new ApiError(responseErrorMessage(body.detail, response.status), response.status);
}
async function checkedResponse(path: string, options: RequestInit = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const mutating = !['GET', 'HEAD'].includes(method);
  const requestSession = sessionRevision;
  if (mutating && !csrfToken) await api<Health>('/api/health');
  if (requestSession !== sessionRevision) throw new ApiError('Die Anmeldung wurde beendet. Bitte erneut anmelden.', 401);
  const requestToken = accessToken;
  const requestCsrf = csrfToken;
  const headers = requestHeaders(options, mutating, requestToken, requestCsrf);
  const response = await fetchResponse(path, options, headers);
  if (!response.ok) await rejectResponse(response, mutating, requestSession, requestCsrf);
  return { response, requestSession };
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { response, requestSession } = await checkedResponse(path, options);
  const body = await response.json().catch(() => ({}));
  if (path === '/api/health' && typeof body.csrf_token === 'string' && sessionRevision === requestSession) csrfToken = body.csrf_token;
  return body as T;
}
export async function downloadFile(path: string, filename: string) {
  const { response } = await checkedResponse(path);
  const expectedType = downloadContentType(filename);
  if (expectedType && response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== expectedType) {
    throw new ApiError('Der Server hat keine gültige Download-Datei geliefert.', 0);
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = filename;
  document.body.appendChild(link);
  try { link.click(); } finally { link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 10000); }
}
function downloadContentType(filename: string) {
  if (filename.endsWith('.pdf')) return 'application/pdf';
  if (filename.endsWith('.zip')) return 'application/zip';
  if (filename.endsWith('.csv')) return 'text/csv';
  return null;
}
export function post<T>(path: string, body?: unknown) {
  return api<T>(path, { method: 'POST', ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
}
export function message(error: unknown) { return error instanceof Error ? error.message : 'Ein unbekannter Fehler ist aufgetreten.'; }
export function useResource<T>(path: string | null, poll = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(Boolean(path));
  const generation = useRef(0);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision(v => v + 1), []);
  useEffect(() => {
    const id = ++generation.current;
    setData(null); setError('');
    if (!path) { setLoading(false); return; }
    const controller = new AbortController();
    let inFlight = false;
    setLoading(true);
    async function load() {
      if (inFlight) return;
      inFlight = true;
      try {
        const value = await api<T>(path!, { signal: controller.signal });
        if (generation.current === id && !controller.signal.aborted) { setData(value); setError(''); }
      } catch (err) {
        if (!controller.signal.aborted && generation.current === id) setError(message(err));
      } finally {
        if (!controller.signal.aborted && generation.current === id) setLoading(false);
        inFlight = false;
      }
    }
    void load();
    const timer = poll ? window.setInterval(load, poll) : undefined;
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [path, revision, poll]);
  return { data, error, loading, refresh };
}
const unsavedForms = new Set<symbol>();
let approvedHash: string | null = null;
const historyIndexKey = '__securityLabRouteIndex';
const historyEpochKey = '__securityLabRouteEpoch';

export function confirmDiscardChanges() {
  return !unsavedForms.size || window.confirm('Ungespeicherte Änderungen verwerfen und die Ansicht verlassen?');
}
export function useUnsavedChanges(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const owner = Symbol('unsaved review');
    unsavedForms.add(owner);
    const before = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', before);
    return () => { unsavedForms.delete(owner); window.removeEventListener('beforeunload', before); };
  }, [dirty]);
}
function navigateHash(hash: string) {
  if (hash === window.location.hash || !confirmDiscardChanges()) return;
  approvedHash = hash;
  window.location.hash = hash;
}
export function navigate(page: string, params: Record<string, string> = {}) {
  const query = new URLSearchParams(params).toString();
  const suffix = query ? `?${query}` : '';
  navigateHash(`#${page}${suffix}`);
}
export function useRoute() {
  const read = () => {
    const [page, query = ''] = window.location.hash.slice(1).split('?');
    return { page: page || 'overview', params: new URLSearchParams(query) };
  };
  const [route, setRoute] = useState(read);
  useEffect(() => {
    let epoch = crypto.randomUUID();
    const index = () => {
      const state = window.history.state;
      if (state?.[historyEpochKey] !== epoch) return null;
      const value = state[historyIndexKey];
      return Number.isSafeInteger(value) ? value as number : null;
    };
    const stamp = (value: number, hash = window.location.hash) => {
      const state = window.history.state;
      window.history.replaceState({ ...(state && typeof state === 'object' ? state : {}), [historyIndexKey]: value, [historyEpochKey]: epoch }, '', `${window.location.pathname}${window.location.search}${hash}`);
    };
    approvedHash = null;
    let accepted = { hash: window.location.hash, index: 0 };
    let restoring = false;
    let restorationTimer: number | undefined;
    const stopRestoring = () => { restoring = false; window.clearTimeout(restorationTimer); };
    const restoreInPlace = () => {
      stopRestoring();
      // Its physical position is unknown. Start a fresh coordinate system so
      // this entry can never share an index with an older history entry.
      epoch = crypto.randomUUID();
      accepted = { ...accepted, index: 0 };
      stamp(accepted.index, accepted.hash);
      approvedHash = null;
    };
    const finishRestoring = () => {
      if (!restoring) return;
      if (window.location.hash === accepted.hash && index() === accepted.index) stopRestoring();
      else restoreInPlace();
    };
    stamp(accepted.index);
    const listener = () => {
      const hash = window.location.hash;
      if (restoring) {
        finishRestoring();
        return;
      }
      const nextIndex = index();
      const approved = approvedHash === hash;
      approvedHash = null;
      if (hash !== accepted.hash && !approved && !confirmDiscardChanges()) {
        // Traverse back to the accepted history entry without unmounting the
        // form. A pre-existing, unmarked entry has no known direction: restore
        // its URL in place instead, still preserving the unsaved form.
        if (nextIndex !== null && nextIndex !== accepted.index) {
          restoring = true;
          // A no-op traversal (or an externally changed history entry) must
          // never leave subsequent navigation disabled indefinitely.
          restorationTimer = window.setTimeout(restoreInPlace, 500);
          window.history.go(accepted.index - nextIndex);
        } else restoreInPlace();
        return;
      }
      // Only an approved in-app hash assignment is known to append one entry.
      // An unmarked Back/Forward target has an unknown physical position.
      if (nextIndex === null && !approved) epoch = crypto.randomUUID();
      const next = nextIndex ?? (approved ? accepted.index + 1 : 0);
      stamp(next);
      accepted = { hash, index: next };
      setRoute(read());
    };
    const click = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element).closest?.('a[href^="#"]') as HTMLAnchorElement | null;
      const hash = anchor?.getAttribute('href');
      if (!hash || hash === '#main-content' || anchor?.target === '_blank' || anchor?.hasAttribute('download')) return;
      event.preventDefault();
      navigateHash(hash);
    };
    window.addEventListener('hashchange', listener);
    window.addEventListener('popstate', finishRestoring);
    document.addEventListener('click', click, true);
    return () => { stopRestoring(); window.removeEventListener('hashchange', listener); window.removeEventListener('popstate', finishRestoring); document.removeEventListener('click', click, true); approvedHash = null; };
  }, []);
  return route;
}
