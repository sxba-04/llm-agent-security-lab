import { afterEach, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

const campaignId = 'campaign-refresh';
const campaignPath = `/api/campaigns/${campaignId}`;
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

function transport({ casesUnavailable = false, conflict = false } = {}) {
  const intervals = new Map<number, () => void>();
  // Keep real resource callbacks; polling is advanced explicitly, not by wall time.
  vi.spyOn(window as Window, 'setInterval').mockImplementation((handler, delay) => {
    if (typeof handler === 'function') intervals.set(delay ?? 0, () => handler());
    return 0;
  });
  const state = { name: 'Stored name', tags: ['stored'], revision: 1, campaignsUnavailable: false, casesUnavailable };
  const requests: { path: string; method: string; signal?: AbortSignal | null }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit = {}) => {
    requests.push({ path, method: options.method || 'GET', signal: options.signal });
    if (path === '/api/health') return response({ csrf_token: 'synthetic-csrf', version: 'test' });
    if (path === '/api/cases') return state.casesUnavailable ? response({ detail: 'Case list unavailable' }, 503) : response({ cases: [] });
    if (path === '/api/campaigns') return state.campaignsUnavailable ? response({ detail: 'Campaign list unavailable' }, 503) : response({ campaigns: [{ campaign_id: campaignId, state: 'completed', created_at: '2026-11-06T10:00:00Z', planned_runs: 0, completed_runs: 0, engineering_only: true, valid_evidence: true, display_name: state.name }] });
    if (path === `${campaignPath}/records`) return response({ records: [] });
    if (path === campaignPath) return response({ manifest: { state: 'completed', schedule: [] }, summary: null });
    if (path === `${campaignPath}/metadata`) {
      if (options.method === 'PUT') {
        if (conflict) return response({ detail: 'Metadata revision conflict' }, 409);
        const values = JSON.parse(options.body as string);
        state.name = values.display_name; state.tags = values.tags; state.revision += 1;
      }
      return response({ display_name: state.name, tags: state.tags, revision: state.revision });
    }
    throw new Error(`Unexpected synthetic request: ${path}`);
  }));
  return { state, requests, pollCampaigns: () => intervals.get(2500)!() };
}

async function editMetadata() {
  window.history.replaceState(null, '', `/#campaigns?id=${campaignId}`);
  render(<App />);
  const user = userEvent.setup();
  await user.click(await screen.findByText('Versuchsname und Tags bearbeiten'));
  const name = screen.getByLabelText('Versuchsname (optional)');
  const tags = screen.getByLabelText('Tags (durch Komma getrennt)');
  await waitFor(() => expect(name).toHaveValue('Stored name'));
  await user.clear(name); await user.type(name, 'Unsaved name');
  await user.clear(tags); await user.type(tags, 'unsaved, local');
  return { user, name, tags };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it.each(['header', 'campaign retry', 'case retry'] as const)('guards dirty metadata before %s, then reloads only after approval', async entry => {
  const api = transport({ casesUnavailable: entry === 'case retry' });
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const { user, name, tags } = await editMetadata();
  if (entry === 'campaign retry') {
    api.state.campaignsUnavailable = true;
    await act(async () => api.pollCampaigns());
    await screen.findByText('Campaign list unavailable');
  }
  const trigger = screen.getByRole('button', { name: entry === 'header' ? 'Aktualisieren' : 'Erneut versuchen' });
  const before = [...api.requests];
  await user.click(trigger);
  expect(name).toBeInTheDocument(); expect(name).toHaveValue('Unsaved name');
  expect(tags).toHaveValue('unsaved, local');
  expect(confirm).toHaveBeenCalledTimes(1);
  expect(api.requests).toEqual(before);
  expect(before.every(request => !request.signal?.aborted)).toBe(true);
  expect(screen.getByRole('button', { name: 'Name und Tags speichern' })).toBeEnabled();

  api.state.name = 'New server name'; api.state.tags = ['server'];
  api.state.casesUnavailable = false; api.state.campaignsUnavailable = false;
  confirm.mockReturnValue(true);
  await user.click(trigger);
  await waitFor(() => expect(name).not.toBeInTheDocument());
  await user.click(await screen.findByText('Versuchsname und Tags bearbeiten'));
  await waitFor(() => expect(screen.getByLabelText('Versuchsname (optional)')).toHaveValue('New server name'));
  expect(screen.getByLabelText('Tags (durch Komma getrennt)')).toHaveValue('server');
  expect(confirm).toHaveBeenCalledTimes(2);
  expect(api.requests.every(request => request.method === 'GET')).toBe(true);
});

it('retains a conflicted metadata draft when header refresh is cancelled', async () => {
  const api = transport({ conflict: true });
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const { user, name, tags } = await editMetadata();
  await user.click(screen.getByRole('button', { name: 'Name und Tags speichern' }));
  await screen.findByText('Metadata revision conflict');
  const before = [...api.requests];
  await user.click(screen.getByRole('button', { name: 'Aktualisieren' }));
  expect(name).toBeInTheDocument();
  expect(confirm).toHaveBeenCalledTimes(1);
  expect(api.requests).toEqual(before);
  expect(name).toHaveValue('Unsaved name'); expect(tags).toHaveValue('unsaved, local');
});

it('refreshes saved metadata without an unnecessary discard dialog', async () => {
  transport();
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const { user, name } = await editMetadata();
  await user.click(screen.getByRole('button', { name: 'Name und Tags speichern' }));
  await screen.findByText('Name und Tags gespeichert.');
  await waitFor(() => expect(name).toBeEnabled());
  await user.click(screen.getByRole('button', { name: 'Aktualisieren' }));
  await waitFor(() => expect(name).not.toBeInTheDocument());
  await user.click(await screen.findByText('Versuchsname und Tags bearbeiten'));
  await waitFor(() => expect(screen.getByLabelText('Versuchsname (optional)')).toHaveValue('Unsaved name'));
  expect(screen.getByLabelText('Tags (durch Komma getrennt)')).toHaveValue('unsaved, local');
  expect(confirm).not.toHaveBeenCalled();
});
