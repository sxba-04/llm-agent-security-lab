import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.stubEnv('VITE_HOSTED', 'true');
vi.stubEnv('VITE_API_BASE_URL', 'https://lab.example');
const { api, downloadFile, sessionIsAuthenticated, signIn, signOut } = await import('./api');
const { AccessGate } = await import('./AccessGate');
const { DownloadButton } = await import('./DownloadButton');
const code = 'test-only-access-code-with-at-least-32-characters';
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => { signOut(); });
afterEach(() => { cleanup(); signOut(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('protected online workbench', () => {
  it('authenticates before mounting the workbench and never persists the code', async () => {
    const fetch = vi.fn(async (_url: string, _options: RequestInit) => json({ csrf_token: 'csrf' }));
    vi.stubGlobal('fetch', fetch);
    const localWrite = vi.spyOn(Storage.prototype, 'setItem');
    render(<AccessGate><p>Private Werkbank</p></AccessGate>);
    expect(screen.queryByText('Private Werkbank')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Zugangscode'), code);
    await user.click(screen.getByRole('button', { name: 'Werkbank öffnen' }));
    expect(await screen.findByText('Private Werkbank')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith('https://lab.example/api/health', expect.objectContaining({ credentials: 'omit', redirect: 'error' }));
    const options = fetch.mock.calls[0][1] as RequestInit;
    expect(new Headers(options.headers).get('Authorization')).toBe(`Bearer ${code}`);
    expect(localWrite).not.toHaveBeenCalled();
    expect(window.location.href).not.toContain(code);
    expect(document.cookie).not.toContain(code);
  });

  it('keeps rejected credentials outside the workbench and shows a useful error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ detail: 'Zugangscode ungültig.' }, 401)));
    render(<AccessGate><p>Private Werkbank</p></AccessGate>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Zugangscode'), code);
    await user.click(screen.getByRole('button', { name: 'Werkbank öffnen' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Zugangscode ungültig.');
    expect(screen.queryByText('Private Werkbank')).not.toBeInTheDocument();
    expect(sessionIsAuthenticated()).toBe(false);
  });

  it('sends bearer and mutation token for writes while keeping multipart boundaries browser-managed', async () => {
    const fetch = vi.fn(async (_url: string, _options: RequestInit) => json({ csrf_token: 'csrf' }));
    vi.stubGlobal('fetch', fetch);
    await signIn(code);
    await api('/api/campaigns', { method: 'POST', body: '{}' });
    let headers = new Headers(fetch.mock.calls[1][1].headers);
    expect(headers.get('Authorization')).toBe(`Bearer ${code}`);
    expect(headers.get('X-Lab-Token')).toBe('csrf');
    expect(headers.get('Content-Type')).toBe('application/json');
    const form = new FormData(); form.append('file', new File(['pdf'], 'article.pdf'));
    await api('/api/documents', { method: 'POST', body: form });
    headers = new Headers(fetch.mock.calls[2][1].headers);
    expect(headers.has('Content-Type')).toBe(false);
    expect(headers.get('X-Lab-Token')).toBe('csrf');
  });

  it('expires the session on a 401 and does not replay a failed mutation', async () => {
    const fetch = vi.fn(async (_url: string, _options: RequestInit) => json({ csrf_token: 'csrf' }));
    vi.stubGlobal('fetch', fetch);
    await signIn(code);
    fetch.mockImplementation(async () => json({ detail: 'Bitte erneut anmelden.' }, 401));
    await expect(api('/api/campaigns', { method: 'POST', body: '{}' })).rejects.toThrow('Bitte erneut anmelden.');
    expect(sessionIsAuthenticated()).toBe(false);
    expect(fetch).toHaveBeenCalledTimes(2);
    await expect(api('/api/cases')).rejects.toThrow('Bitte zuerst anmelden.');
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('downloads bytes with authentication and rejects errors instead of saving them as PDFs', async () => {
    const fetch = vi.fn(async (_url: string, _options: RequestInit) => json({ csrf_token: 'csrf' }));
    vi.stubGlobal('fetch', fetch);
    const objectUrl = vi.fn(() => 'blob:checked-pdf');
    vi.stubGlobal('URL', class extends URL { static createObjectURL = objectUrl; static revokeObjectURL = vi.fn(); });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    await signIn(code);
    fetch.mockImplementation(async () => new Response('%PDF-1.7', { headers: { 'Content-Type': 'application/pdf' } }));
    await downloadFile('/api/cases/dev-g1-01/articles/clean/pdf', 'article.pdf');
    expect(new Headers(fetch.mock.calls[1][1].headers).get('Authorization')).toBe(`Bearer ${code}`);
    expect(objectUrl).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    fetch.mockImplementation(async () => json({ detail: 'PDF konnte nicht erstellt werden.' }, 500));
    render(<DownloadButton path="/api/cases/dev-g1-01/articles/clean/pdf" filename="article.pdf" className="button">PDF laden</DownloadButton>);
    await userEvent.setup().click(screen.getByRole('button', { name: 'PDF laden' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('PDF konnte nicht erstellt werden.');
    expect(objectUrl).toHaveBeenCalledTimes(1);
  });

  it('never forwards the credential to an external request path', async () => {
    const fetch = vi.fn(async (_url: string, _options: RequestInit) => json({ csrf_token: 'csrf' }));
    vi.stubGlobal('fetch', fetch);
    await signIn(code);
    await expect(api('https://other.example/api/cases')).rejects.toThrow();
    await expect(api('/api/../../anything')).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('rejects an HTML error page even when a hosting proxy returns HTTP 200', async () => {
    const fetch = vi.fn(async () => new Response('<html>Wrong service</html>', { headers: { 'Content-Type': 'text/html' } }));
    vi.stubGlobal('fetch', fetch);
    await expect(signIn(code)).rejects.toThrow('keine gültige Werkbank-Sitzung');
    expect(sessionIsAuthenticated()).toBe(false);
    fetch.mockImplementation(async () => json({ csrf_token: 'csrf' }));
    await signIn(code);
    fetch.mockImplementation(async () => new Response('<html>Wrong service</html>', { headers: { 'Content-Type': 'text/html' } }));
    await expect(downloadFile('/api/cases/test/articles/clean/pdf', 'article.pdf')).rejects.toThrow('keine gültige Download-Datei');
  });
});
