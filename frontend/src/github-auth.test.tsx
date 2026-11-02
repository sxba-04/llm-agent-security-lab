import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.stubEnv('VITE_HOSTED', 'true');
vi.stubEnv('VITE_API_BASE_URL', 'https://lab.example');
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const state = 'a'.repeat(43), token = 's'.repeat(43), code = 'test-only-access-code-with-at-least-32-characters';
const user = { id: 12345, login: 'test-researcher', role: 'researcher', permissions: ['read', 'write', 'manage_own_sessions'] };
const pendingKey = 'security-lab-github-pkce';
beforeEach(() => { vi.resetModules(); window.sessionStorage.clear(); window.localStorage.clear(); window.history.replaceState({}, '', '/'); vi.stubGlobal('crypto', webcrypto); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
function pendingReturn(params = `code=github-one-time-code&state=${state}`, expiresAt = Date.now() + 600_000) {
  window.sessionStorage.setItem(pendingKey, JSON.stringify({ state, verifier: 'v'.repeat(43), expiresAt }));
  window.history.replaceState({}, '', `/?${params}#overview`);
}
function startResponse(options: RequestInit, changes: Record<string, string> = {}) {
  const body = JSON.parse(String(options.body));
  const url = new URL('https://github.com/login/oauth/authorize');
  url.search = new URLSearchParams({ state, redirect_uri: `${window.location.origin}${window.location.pathname}`, code_challenge: body.code_challenge, code_challenge_method: 'S256', ...changes }).toString();
  return { authorization_url: url.href, state, expires_in: 600 };
}

describe('GitHub OAuth browser boundary', () => {
  it('stores only transient PKCE data and sends no authorization on the public auth request', async () => {
    const fetch = vi.fn(async (_url: string, options: RequestInit) => json(startResponse(options))); vi.stubGlobal('fetch', fetch);
    const { startGitHubLogin } = await import('./github-auth');
    const target = new URL(await startGitHubLogin());
    const pending = JSON.parse(window.sessionStorage.getItem(pendingKey)!);
    expect(Object.keys(pending).sort()).toEqual(['expiresAt', 'state', 'verifier']);
    expect(pending.verifier).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(target.origin).toBe('https://github.com');
    expect(target.searchParams.get('code_challenge')).not.toBe(pending.verifier);
    expect(window.localStorage.length).toBe(0);
    expect(new Headers(fetch.mock.calls[0][1].headers).has('Authorization')).toBe(false);
    expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'POST', credentials: 'omit', redirect: 'error', cache: 'no-store' });
  });
  it.each(['https://evil.example/login/oauth/authorize', 'https://github.com/settings/profile'])('rejects an unexpected navigation target %s', async maliciousUrl => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options: RequestInit) => json({ ...startResponse(options), authorization_url: maliciousUrl })));
    const { startGitHubLogin } = await import('./github-auth');
    await expect(startGitHubLogin()).rejects.toThrow('nicht korrekt konfiguriert');
    expect(window.sessionStorage.getItem(pendingKey)).toBeNull();
  });
  it.each<Record<string, string>>([{ state: 'mismatched-state' }, { code_challenge: 'different-challenge' }, { redirect_uri: 'https://evil.example/' }, { code_challenge_method: 'plain' }])('rejects mismatched OAuth parameters %j', async changes => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options: RequestInit) => json(startResponse(options, changes))));
    const { startGitHubLogin } = await import('./github-auth');
    await expect(startGitHubLogin()).rejects.toThrow('nicht korrekt konfiguriert');
    expect(window.sessionStorage.getItem(pendingKey)).toBeNull();
  });
  it('explains when temporary browser storage is blocked', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options: RequestInit) => json(startResponse(options))));
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Denied', 'SecurityError'); });
    const { startGitHubLogin } = await import('./github-auth');
    await expect(startGitHubLogin()).rejects.toThrow('verwende deinen Zugangscode');
  });
  it('scrubs callback data before network calls and completes a StrictMode callback only once', async () => {
    pendingReturn(`code=github-one-time-code&state=${state}&view=lab`);
    const fetch = vi.fn(async (url: string, options: RequestInit) => {
      expect(window.location.search).toBe('?view=lab');
      expect(window.sessionStorage.getItem(pendingKey)).toBeNull();
      if (url.endsWith('/complete')) {
        expect(JSON.parse(String(options.body))).toEqual({ code: 'github-one-time-code', state, code_verifier: 'v'.repeat(43) });
        expect(new Headers(options.headers).has('Authorization')).toBe(false);
        return json({ access_token: token, user });
      }
      expect(new Headers(options.headers).get('Authorization')).toBe(`Bearer ${token}`);
      return json({ csrf_token: 'csrf', user });
    }); vi.stubGlobal('fetch', fetch);
    const { finishGitHubReturn } = await import('./github-auth');
    const api = await import('./api');
    const first = finishGitHubReturn(); expect(finishGitHubReturn()).toBe(first);
    await expect(first).resolves.toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(api.sessionIdentity()).toEqual(user); expect(api.sessionIsAuthenticated()).toBe(true);
    expect(window.location.href).not.toContain(token);
    expect(window.sessionStorage.length).toBe(0); expect(window.localStorage.length).toBe(0);
  });
  it.each([
    ['code=github-code&state=wrong', 'nicht zugeordnet'],
    [`code=github-code&state=${state}&state=${state}`, 'nicht zugeordnet'],
    [`code=one&code=two&state=${state}`, 'unvollständig'],
    [`error=access_denied&error_description=UNTRUSTED&state=${state}`, 'abgebrochen'],
  ])('rejects unsafe or denied callback %s without exchange', async (query, text) => {
    pendingReturn(query); const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const { finishGitHubReturn } = await import('./github-auth');
    await expect(finishGitHubReturn()).rejects.toThrow(text);
    expect(window.location.search).toBe(''); expect(window.sessionStorage.length).toBe(0); expect(fetch).not.toHaveBeenCalled();
  });
  it.each(['missing', 'expired'])('rejects %s browser state before exchange', async status => {
    pendingReturn(undefined, status === 'expired' ? Date.now() - 1 : undefined);
    if (status === 'missing') window.sessionStorage.clear();
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const { finishGitHubReturn } = await import('./github-auth');
    await expect(finishGitHubReturn()).rejects.toThrow(status === 'expired' ? 'abgelaufen' : 'nicht zu dieser Browsersitzung');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('shows account denial without establishing a session', async () => {
    pendingReturn(); vi.stubGlobal('fetch', vi.fn(async () => json({ detail: 'Dieses GitHub-Konto ist nicht freigegeben.' }, 403)));
    const { finishGitHubReturn } = await import('./github-auth');
    await expect(finishGitHubReturn()).rejects.toThrow('nicht freigegeben');
    const api = await import('./api'); expect(api.sessionIsAuthenticated()).toBe(false); expect(api.sessionIdentity()).toBeNull();
  });
  it('cannot replace a newer access-code session with a delayed OAuth completion', async () => {
    pendingReturn(); let finish!: (response: Response) => void;
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/complete') ? new Promise<Response>(resolve => { finish = resolve; }) : json({ csrf_token: 'new-session' })));
    const { finishGitHubReturn } = await import('./github-auth'); const api = await import('./api');
    const oldCallback = finishGitHubReturn(); await api.signIn(code); finish(json({ access_token: token, user }));
    await expect(oldCallback).rejects.toThrow('Anmeldung wurde beendet');
    expect(api.sessionIsAuthenticated()).toBe(true); expect(api.sessionIdentity()).toBeNull();
  });
  it('revokes logout using captured credentials without affecting a newer login', async () => {
    let finishLogout!: (response: Response) => void;
    const fetch = vi.fn(async (url: string, _options: RequestInit) => url.endsWith('/logout') ? new Promise<Response>(resolve => { finishLogout = resolve; }) : json({ csrf_token: 'csrf', user })); vi.stubGlobal('fetch', fetch);
    const api = await import('./api'); await api.signInWithGitHubSession(token, api.sessionGeneration());
    const logout = api.signOut(); expect(api.sessionIsAuthenticated()).toBe(false); expect(api.sessionIdentity()).toBeNull();
    const options = fetch.mock.calls[1][1];
    expect(new Headers(options.headers).get('Authorization')).toBe(`Bearer ${token}`); expect(new Headers(options.headers).get('X-Lab-Token')).toBe('csrf');
    await api.signIn(code); finishLogout(json({ detail: 'Unavailable' }, 503)); await logout;
    expect(api.sessionIsAuthenticated()).toBe(true); expect(api.sessionMessage()).toBe('');
  });
  it('explains GitHub expiry without claiming the access code is invalid', async () => {
    const fetch = vi.fn(async () => json({ csrf_token: 'csrf', user })); vi.stubGlobal('fetch', fetch);
    const api = await import('./api'); await api.signInWithGitHubSession(token, api.sessionGeneration());
    fetch.mockResolvedValueOnce(json({ detail: 'Session expired' }, 401));
    await expect(api.api('/api/cases')).rejects.toThrow('Session expired');
    expect(api.sessionMessage()).toContain('GitHub-Sitzung ist abgelaufen'); expect(api.sessionIdentity()).toBeNull();
  });
});

describe('GitHub login and session controls', () => {
  it('offers GitHub only when enabled and retains access-code login', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ github_enabled: true })));
    const { AccessGate } = await import('./AccessGate'); render(<AccessGate><p>Private Werkbank</p></AccessGate>);
    expect(await screen.findByRole('button', { name: 'Mit GitHub anmelden' })).toBeEnabled();
    expect(screen.getByLabelText('Zugangscode')).toBeEnabled();
  });
  it('recovers failed discovery without blocking the access code', async () => {
    const fetch = vi.fn(async () => json({ detail: 'Unavailable' }, 503)); vi.stubGlobal('fetch', fetch);
    const { AccessGate } = await import('./AccessGate'); render(<AccessGate><p>Private Werkbank</p></AccessGate>);
    expect(await screen.findByRole('status')).toHaveTextContent('Dein Zugangscode bleibt verfügbar');
    fetch.mockResolvedValueOnce(json({ github_enabled: true })); await userEvent.setup().click(screen.getByRole('button', { name: 'Erneut prüfen' }));
    expect(await screen.findByRole('button', { name: 'Mit GitHub anmelden' })).toBeEnabled();
  });
  it('revokes another own session while keeping the current browser signed in', async () => {
    const now = '2026-11-02T12:00:00+00:00'; let otherPresent = true;
    const fetch = vi.fn(async (url: string, options?: RequestInit) => {
      if (url.endsWith('/api/health')) return json({ csrf_token: 'csrf', user });
      if (options?.method === 'DELETE') { otherPresent = false; return json({ revoked: true }); }
      return json({ sessions: [{ id: 'current', created_at: now, expires_at: now, current: true }, ...(otherPresent ? [{ id: 'another', created_at: now, expires_at: now, current: false }] : [])] });
    }); vi.stubGlobal('fetch', fetch);
    const api = await import('./api'); await api.signInWithGitHubSession(token, api.sessionGeneration());
    const { SessionMenu } = await import('./SessionMenu'); render(<SessionMenu />);
    const actor = userEvent.setup(); await actor.click(screen.getByRole('button', { name: '@test-researcher' }));
    expect(await screen.findByText('Diese Sitzung')).toBeVisible(); await actor.click(screen.getByRole('button', { name: 'Beenden' }));
    await waitFor(() => expect(screen.queryByText('Weitere Sitzung')).not.toBeInTheDocument()); expect(api.sessionIsAuthenticated()).toBe(true);
    const deletion = fetch.mock.calls.find(([, options]) => options?.method === 'DELETE');
    expect(deletion?.[0]).toBe('https://lab.example/api/auth/sessions/another'); expect(new Headers(deletion?.[1]?.headers).get('X-Lab-Token')).toBe('csrf');
    await actor.keyboard('{Escape}'); expect(screen.queryByRole('region', { name: 'Deine Sitzungen' })).not.toBeInTheDocument();
  });
});

describe('GitHub recovery feedback', () => {
  it('shows login-start failure and re-enables the alternative code form', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/config') ? json({ github_enabled: true }) : json({ detail: 'Zu viele Anmeldeversuche.' }, 429)));
    const { AccessGate } = await import('./AccessGate'); render(<AccessGate><p>Private Werkbank</p></AccessGate>);
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Mit GitHub anmelden' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Zu viele Anmeldeversuche.');
    expect(screen.getByLabelText('Zugangscode')).toBeEnabled();
  });
  it('handles callback denial inside the gate and permits code recovery without replaying the callback', async () => {
    pendingReturn();
    const fetch = vi.fn(async (url: string) => {
      if (url.endsWith('/complete')) return json({ detail: 'Dieses GitHub-Konto ist nicht freigegeben.' }, 403);
      if (url.endsWith('/config')) return json({ github_enabled: true });
      return json({ csrf_token: 'csrf' });
    }); vi.stubGlobal('fetch', fetch);
    const { AccessGate } = await import('./AccessGate'); render(<AccessGate><p>Private Werkbank</p></AccessGate>);
    expect(await screen.findByRole('alert')).toHaveTextContent('nicht freigegeben');
    await waitFor(() => expect(screen.getByLabelText('Zugangscode')).toBeEnabled());
    const actor = userEvent.setup(); await actor.type(screen.getByLabelText('Zugangscode'), code); await actor.click(screen.getByRole('button', { name: 'Werkbank öffnen' }));
    expect(await screen.findByText('Private Werkbank')).toBeVisible();
    expect(fetch.mock.calls.filter(([url]) => url.endsWith('/complete'))).toHaveLength(1);
    const { finishGitHubReturn } = await import('./github-auth'); expect(finishGitHubReturn()).toBeNull();
  });
  it('reports uncertain server logout while clearing local credentials immediately', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/logout') ? json({ detail: 'Unavailable' }, 503) : json({ csrf_token: 'csrf', user })));
    const api = await import('./api'); await api.signInWithGitHubSession(token, api.sessionGeneration()); await api.signOut();
    expect(api.sessionIsAuthenticated()).toBe(false); expect(api.sessionIdentity()).toBeNull();
    expect(api.sessionMessage()).toContain('Server konnte die Sitzung nicht bestätigen');
  });
  it('does not accept a malformed identity as a signed-in GitHub account', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ csrf_token: 'csrf', user: { ...user, id: -1 } })));
    const api = await import('./api');
    await expect(api.signInWithGitHubSession(token, api.sessionGeneration())).rejects.toThrow('keine gültige GitHub-Identität');
    expect(api.sessionIsAuthenticated()).toBe(false); expect(api.sessionIdentity()).toBeNull();
  });
  it('rejects broken transient callback storage without sending the code', async () => {
    pendingReturn(); window.sessionStorage.setItem(pendingKey, '{invalid');
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    const { finishGitHubReturn } = await import('./github-auth');
    await expect(finishGitHubReturn()).rejects.toThrow('nicht zu dieser Browsersitzung'); expect(fetch).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem(pendingKey)).toBeNull();
  });
});
