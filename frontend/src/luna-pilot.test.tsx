import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';

vi.stubEnv('VITE_HOSTED', 'true');
vi.stubEnv('VITE_API_BASE_URL', 'https://lab.example');
const { default: App } = await import('./App');
const { signIn, signOut } = await import('./api');
const { LunaPilotPage } = await import('./LunaPilot');

const path = 'https://lab.example/api/pilot/luna';
const planPath = 'https://lab.example/api/studies/clean-b/plan';
const runPath = 'https://lab.example/api/studies/clean-b/run';
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

function backend(pilot: (options: RequestInit) => Response | Promise<Response>, capabilities = ['luna_pilot_v1'],
  plan?: () => Response, run?: (options: RequestInit) => Response | Promise<Response>) {
  const fetch = vi.fn(async (url: string, options: RequestInit) => {
    if (url === path) return pilot(options);
    if (url === runPath && run) return run(options);
    if (url === planPath && plan) return plan();
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
  expect(screen.getByRole('status')).toHaveTextContent('Status: Läuft');
  running = false;
  await userEvent.setup().click(screen.getByRole('button', { name: 'Status aktualisieren' }));
  expect(await screen.findByText('Nicht bestanden')).toBeVisible();
  expect(screen.getAllByText('Unvollständig belegt')).toHaveLength(4);
  expect(fetch.mock.calls.some(([, options]) => options.method === 'POST')).toBe(false);
});

it('shows reported tokens when the applied tariff cannot be priced', async () => {
  backend(() => reply({ state: 'failed', result: { ...finished.result, status: 'technical_error',
    technical_acceptance: false, estimated_cost_eur: null } }));
  await signIn(code);
  render(<LunaPilotPage />);
  expect(await screen.findByText('Beendet mit Fehler')).toBeVisible();
  expect(screen.getByText('300')).toBeVisible();
  expect(screen.getByText('22')).toBeVisible();
  expect(screen.getByText('Unvollständig belegt')).toBeVisible();
});

it.each(['disabled', 'failed'])('prevents starting in state %s even without a result', async state => {
  backend(() => reply({ state, result: null }));
  await signIn(code);
  render(<LunaPilotPage />);
  await screen.findByText(state === 'disabled' ? 'Noch nicht freigeschaltet' : 'Beendet mit Fehler');
  expect(screen.queryByRole('button', { name: 'Luna-Pilot starten' })).not.toBeInTheDocument();
});

const schedule = [1, 2, 3].flatMap(group => [1, 2, 3, 4].map(index => ({
  case_id: `DEV-G${group}-0${index}`, variant: 'B', source: 'clean', repetition: 1,
})));
const cleanPlan = {
  plan_id: 'clean-b-test-plan', schedule, paid_run_authorized: false,
  model_profile: { model: 'gpt-6-luna', reasoning_effort: 'none', service_tier: 'default' },
  limits: { max_model_calls: 4, max_tool_calls: 3, timeout_seconds: 120 },
  budget: { max_requests: 48, planned_max_eur: '0.21823488', proposed_run_cap_eur: '0.50' },
  acceptance: { min_correct: 10, max_fundamental_tool_errors: 0 },
};

it('opens the read-only B plan with its own capability and lists the scheduled cases in order', async () => {
  const fetch = backend(() => reply(finished), ['clean_b_plan_v1'], () => reply(cleanPlan));
  await signIn(code);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('link', { name: 'B-Versuchsplan' }));
  expect(await screen.findByText('clean-b-test-plan')).toBeVisible();
  expect(screen.getByText('10 von 12')).toBeVisible();
  expect(screen.getByText('PLANUNG', { exact: true })).toBeVisible();
  expect(screen.getByText(/0,21823488/)).toBeVisible();
  expect(screen.getByText('gpt-6-luna')).toBeVisible();
  expect(screen.queryByRole('link', { name: 'Luna-Pilot' })).not.toBeInTheDocument();
  await user.click(screen.getByText('Geplante Fallfolge (12)'));
  expect(screen.getByRole('list', { name: 'Geplante Fallfolge' })).toBeVisible();
  expect(screen.getAllByRole('listitem').map(item => item.textContent)).toEqual(schedule.map(row => row.case_id));
  expect(screen.queryByRole('button', { name: /starten/i })).not.toBeInTheDocument();
  const calls = fetch.mock.calls.filter(([url]) => url === planPath);
  expect(calls).toHaveLength(1);
  expect(calls[0][1].method || 'GET').toBe('GET');
  expect(new Headers(calls[0][1].headers).get('Authorization')).toBe('Bearer ' + code);
  expect(fetch.mock.calls.some(([url, init]) => url === path || url === runPath || init.method === 'POST')).toBe(false);
});

it('keeps the B plan hidden on a backend that only supports A17, even for a direct route', async () => {
  const fetch = backend(() => reply(finished));
  await signIn(code);
  window.location.hash = '#clean-b-plan';
  render(<App />);
  await screen.findByRole('link', { name: 'Luna-Pilot' });
  expect(screen.queryByRole('link', { name: 'B-Versuchsplan' })).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url === planPath)).toBe(false);
});

it.each([
  ['HTTP failure', () => reply({ detail: 'Katalogprüfung fehlgeschlagen.' }, 503)],
  ['a missing schedule row', () => reply({ ...cleanPlan, schedule: [null] })],
  ['an object as the case ID', () => reply({ ...cleanPlan, schedule: [{ ...schedule[0], case_id: {} }] })],
  ['a duplicate case', () => reply({ ...cleanPlan, schedule: [schedule[0], schedule[0]] })],
  ['an unrelated source', () => reply({ ...cleanPlan, schedule: [{ ...schedule[0], source: 'other' }] })],
  ['an object as the minimum score', () => reply({ ...cleanPlan, acceptance: { ...cleanPlan.acceptance, min_correct: {} } })],
  ['an unusable budget amount', () => reply({ ...cleanPlan, budget: { ...cleanPlan.budget, planned_max_eur: 'invalid' } })],
  ['unknown plan semantics', () => reply({ ...cleanPlan, paid_run_authorized: true })],
])('keeps historical pilot evidence accessible after %s', async (_name, planResponse) => {
  const fetch = backend(() => reply(finished), ['luna_pilot_v1', 'clean_b_plan_v1'], planResponse);
  await signIn(code);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('link', { name: 'B-Versuchsplan' }));
  expect(await screen.findByRole('alert')).toBeVisible();
  await user.click(screen.getByRole('link', { name: 'Luna-Pilot' }));
  expect(await screen.findByText(finished.result.final_text)).toBeVisible();
  expect(fetch.mock.calls.some(([, options]) => options.method === 'POST')).toBe(false);
});

async function openCleanBRun(run: (options: RequestInit) => Response | Promise<Response>, plan = cleanPlan) {
  const fetch = backend(() => reply(finished), ['clean_b_plan_v1', 'clean_b_run_v1'], () => reply(plan), run);
  await signIn(code);
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('link', { name: 'B-Versuchsplan' }));
  return { user, requests: () => fetch.mock.calls.filter(([url]) => url === runPath).map(([, init]) => init) };
}
function runStatus(state: string, recorded_runs: number | null = 0) {
  return reply({ state, planned_runs: 12, recorded_runs });
}

it('confirms the fixed cost and scope before sending at most one bodyless authenticated B start', async () => {
  let started = false;
  const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValue(true);
  const { user, requests } = await openCleanBRun(options => {
    if (options.method === 'POST') started = true;
    return started ? runStatus('completed', 12) : runStatus('ready');
  });
  const button = await screen.findByRole('button', { name: 'B-Serie starten' });
  await user.click(button);
  expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/zwölf.*0,50 €/));
  expect(requests()).toHaveLength(1);
  await user.dblClick(button);
  expect(await screen.findByText('12 von 12 Laufbelegen gespeichert.')).toBeVisible();
  expect(screen.getByText(/technisch abgeschlossen/)).toBeVisible();
  const writes = requests().filter(init => init.method === 'POST');
  expect(writes).toHaveLength(1);
  expect(writes[0].body).toBeUndefined();
  expect(new Headers(writes[0].headers).get('Authorization')).toBe('Bearer ' + code);
  expect(new Headers(writes[0].headers).get('X-Lab-Token')).toBe('csrf');
  expect(screen.queryByRole('button', { name: 'B-Serie starten' })).not.toBeInTheDocument();
});

it('uses only status reads after an unacknowledged B start, including when reopening the plan', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  const { user, requests } = await openCleanBRun(options => options.method === 'POST'
    ? Promise.reject(new TypeError('Response lost')) : runStatus('ready'));
  await user.click(await screen.findByRole('button', { name: 'B-Serie starten' }));
  expect(await screen.findByText(/liegt keine Bestätigung vor/)).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Serienstatus aktualisieren' }));
  await user.click(screen.getByRole('link', { name: 'Übersicht' }));
  await user.click(screen.getByRole('link', { name: 'B-Versuchsplan' }));
  expect(await screen.findByText(/Startanfrage wurde ausgelöst/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'B-Serie starten' })).not.toBeInTheDocument();
  expect(requests().filter(r => r.method === 'POST')).toHaveLength(1);
});

it('automatically reads new counts for a running series and displays its stopped state', async () => {
  let running = true;
  const { requests } = await openCleanBRun(() => running ? runStatus('running', 3) : runStatus('stopped', 4));
  expect(await screen.findByText('3 von 12 Laufbelegen gespeichert.')).toBeVisible();
  expect(screen.getByText(/automatisch aktualisiert/)).toBeVisible();
  running = false;
  expect(await screen.findByText('4 von 12 Laufbelegen gespeichert.', {}, { timeout: 8000 })).toBeVisible();
  expect(screen.getByText(/wurde gestoppt/)).toBeVisible();
  expect(requests().every(r => r.method !== 'POST')).toBe(true);
}, 10000);

it.each([
  ['disabled', 0, 'noch nicht zum Start freigegeben'],
  ['interrupted', 1, 'wurde unterbrochen'],
  ['unavailable', null, 'nicht verlässlich bestimmen'],
  ['completed', 10, 'keinen lesbaren Serienstatus'],
  ['ready', 1, 'keinen lesbaren Serienstatus'],
] as const)('keeps %s read-only and reports unavailable evidence honestly', async (state, count, label) => {
  const { requests } = await openCleanBRun(() => runStatus(state, count));
  expect(await screen.findByText(new RegExp(label))).toBeVisible();
  expect(screen.queryByRole('button', { name: 'B-Serie starten' })).not.toBeInTheDocument();
  if (count === null) expect(screen.queryByText(/Laufbelegen gespeichert/)).not.toBeInTheDocument();
  expect(requests().every(r => r.method !== 'POST')).toBe(true);
});

it('withholds the start action if the advertised budget differs from the fixed confirmation', async () => {
  await openCleanBRun(() => runStatus('ready'), { ...cleanPlan, budget: { ...cleanPlan.budget, proposed_run_cap_eur: '1' } });
  expect(await screen.findByRole('alert')).toHaveTextContent('Fallzahl oder Seriengrenze');
  expect(screen.queryByRole('button', { name: 'B-Serie starten' })).not.toBeInTheDocument();
});
