import { useCallback, useEffect, useRef, useState } from 'react';
import type { Health } from './types';

let csrfToken = '';
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = options.method || 'GET';
  const mutating = !['GET', 'HEAD'].includes(method);
  if (mutating && !csrfToken) await api<Health>('/api/health');
  const headers = new Headers(options.headers);
  if (mutating) headers.set('X-Lab-Token', csrfToken);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response: Response;
  try { response = await fetch(path, { ...options, headers, credentials: 'same-origin' }); }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('Die lokale Werkbank ist nicht erreichbar. Prüfe, ob der Python-Prozess noch läuft.', 0);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.slice(1).join('.') || 'Eingabe'}: ${item.msg || 'ungültig'}`).join(' · ')
      : `Die Anfrage konnte nicht verarbeitet werden (${response.status}).`;
    throw new ApiError(message, response.status);
  }
  if (path === '/api/health' && body.csrf_token) csrfToken = body.csrf_token;
  return body as T;
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
export function navigate(page: string, params: Record<string, string> = {}) {
  const query = new URLSearchParams(params).toString();
  window.location.hash = `${page}${query ? `?${query}` : ''}`;
}
export function useRoute() {
  const read = () => {
    const [page, query = ''] = window.location.hash.slice(1).split('?');
    return { page: page || 'overview', params: new URLSearchParams(query) };
  };
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const listener = () => setRoute(read());
    window.addEventListener('hashchange', listener);
    return () => window.removeEventListener('hashchange', listener);
  }, []);
  return route;
}
