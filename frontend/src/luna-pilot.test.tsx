import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';

vi.stubEnv('VITE_HOSTED', 'true');
vi.stubEnv('VITE_API_BASE_URL', 'https://lab.example');
const { default: App } = await import('./App');
const { signIn, signOut } = await import('./api');
const { LunaPilotPage } = await import('./LunaPilot');

const path = 'https://lab.example/api/pilot/luna';
const code = 'test-only-access-code-with-at-least-32-characters';
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});
const finished = {
  state: 'completed',
  result: {
    status: 'completed', technical_acceptance: true, final_text: 'Antwort zum freigegebenen Ticket.',
    models: ['gpt-6-luna-2026-11-09'], model_calls: 2, tool_calls: 1,
    input_tokens: 300, output_tokens: 22, estimated_cost_eur: '0.0000492',
  },
};

function backend(pilot: (options: RequestInit) => Response | Promise<Response>, capabilities = ['luna_pilot_v1']) {
  const fetch = vi.fn(async (url: string, options: RequestInit) => {
    if (url === path) return pilot(options);
    if (url.endsWith('/api/health')) return reply({ csrf_token: 'csrf', capabilities });
    if (url.endsWith('/api/cases')) return reply({ cases: [] });
    if (url.endsWith('/api/campaigns')) return reply({ campaigns: [] });
    if (url.endsWith('/api/auth/config')) return reply({ github_enabled: false });
    throw new Error('Unexpected test request');
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

afterEach(() => {
  cleanup();
  void signOut();
  history.replaceState(null, '', '#overview');
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('protects the pilot entry point and hides it for older backends', async () => {
  const fetch = backend(() => reply({ state: 'disabled', result: null }), []);
  window.location.hash = '#pilot';
  const { unmount } = render(<App />);
  await screen.findByRole('heading', { name: 'Willkommen im Labor.' });
  expect(screen.queryByRole('link', { name: 'Luna-Pilot' })).not.toBeInTheDocument();
  unmount();
  await signIn(code);
  render(<App />);
  await screen.findByRole('heading', { name: 'Sicherheit sichtbar machen.' });
  expect(screen.queryByRole('link', { name: 'Luna-Pilot' })).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url === path)).toBe(false);
});

it('starts one fixed paid POST from the hosted navigation and reads the receipt after remount', async () => {
  let complete: (() => void) | undefined;
  let settled = false;
  const fetch = backend(async options => {
    if (options.method === 'POST') {
      await new Promise<void>(resolve => { complete = resolve; });
      settled = true;
    }
    return reply(settled ? finished : { state: 'ready', result: null });
  });
  await signIn(code);
  const user = userEvent.setup();
  const { unmount } = render(<App />);
  await user.click(await screen.findByRole('link', { name: 'Luna-Pilot' }));
  const start = await screen.findByRole('button', { name: 'Luna-Pilot starten' });
  expect(screen.getByText('0,50 €')).toBeVisible();
  await user.dblClick(start);
  expect(start).toBeDisabled();
  const writes = () => fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(writes()).toHaveLength(1);
  const [url, request] = writes()[0];
  expect(url).toBe(path);
  expect(request.body).toBeUndefined();
  expect(new Headers(request.headers).get('Authorization')).toBe('Bearer ' + code);
  expect(new Headers(request.headers).get('X-Lab-Token')).toBe('csrf');
  complete!();
  expect(await screen.findByText('Antwort zum freigegebenen Ticket.')).toBeVisible();
  expect(screen.getByText('gpt-6-luna-2026-11-09')).toBeVisible();
  expect(screen.getByText('300')).toBeVisible();
  expect(screen.getByText('22')).toBeVisible();
  expect(screen.getByText(/0,0000492/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Luna-Pilot starten' })).not.toBeInTheDocument();
  unmount();
  render(<LunaPilotPage />);
  expect(await screen.findByText('Antwort zum freigegebenen Ticket.')).toBeVisible();
  expect(writes()).toHaveLength(1);
});

it.each([409, 503])('reconciles an ambiguous start with GET only (HTTP %i)', async status => {
  const fetch = backend(options => options.method === 'POST'
    ? reply({ detail: 'Start konnte nicht bestätigt werden.' }, status)
    : reply({ state: 'ready', result: null }));
  await signIn(code);
  render(<LunaPilotPage />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Luna-Pilot starten' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url === path)).toHaveLength(3));
  expect(await screen.findByRole('alert')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Status aktualisieren' }));
  expect(await screen.findByRole('button', { name: 'Luna-Pilot starten' })).toBeDisabled();
  expect(fetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1);
});

it('recovers a running attempt with a read and labels incomplete billing evidence', async () => {
  let running = true;
  const fetch = backend(() => reply(running ? { state: 'running', result: null } : {
    state: 'failed', result: { ...finished.result, technical_acceptance: false, status: 'technical_error',
      final_text: '', models: [], input_tokens: null, output_tokens: null, estimated_cost_eur: null },
  }));
  await signIn(code);
  render(<LunaPilotPage />);
  expect(await screen.findByText('Läuft')).toBeVisible();
  running = false;
  await userEvent.setup().click(screen.getByRole('button', { name: 'Status aktualisieren' }));
  expect(await screen.findByText('Nicht bestanden')).toBeVisible();
  expect(screen.getAllByText('Unvollständig belegt')).toHaveLength(4);
  expect(fetch.mock.calls.some(([, options]) => options.method === 'POST')).toBe(false);
});

it.each(['disabled', 'failed'])('prevents starting in state %s even without a result', async state => {
  backend(() => reply({ state, result: null }));
  await signIn(code);
  render(<LunaPilotPage />);
  await screen.findByText(state === 'disabled' ? 'Noch nicht freigeschaltet' : 'Beendet mit Fehler');
  expect(screen.queryByRole('button', { name: 'Luna-Pilot starten' })).not.toBeInTheDocument();
});
