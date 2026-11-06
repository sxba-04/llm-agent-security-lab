import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReviewsPage } from './Reviews';
import { LaunchForm } from './Campaigns';
import type { LabCase, Packet } from './types';

const packet: Packet = {review_id: 'packet-test', user_request: 'Synthetic task', article_text: 'Synthetic article', initial_tickets: {}, final_tickets: {}, session: {}, expected: {}, final_text: 'Synthetic answer', status: 'completed', blocked_elements: [], observed_unauthorized_effect: false, rubric: {}};
const makeResponse = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers: {'Content-Type': 'application/json'}});
function reviewTransport(options: { legacy?: boolean; conflict?: boolean } = {}) {
  let saved = false;
  const writes: Record<string, unknown>[] = [];
  const fetch = vi.fn(async (url: string, request: RequestInit = {}) => {
    if (url === '/api/health') return makeResponse({csrf_token: 'test-token'});
    if (url === '/api/reviews') return makeResponse({review_sets: [{review_set_id: 'set-test', campaign_id: 'campaign-test', packet_count: 1, created_at: '2026-11-06T10:00:00Z'}]});
    if (url.endsWith('/packets')) return makeResponse({packets: [packet]});
    if (request.method === 'PUT') {
      const body = JSON.parse(request.body as string); writes.push(body);
      if (options.conflict && !saved) { saved = true; return makeResponse({detail: 'Ein anderer Tab hat gespeichert.'}, 409); }
      saved = true; return makeResponse({saved: 1, complete: false, revision: Number(body.expected_revision) + 1});
    }
    return makeResponse({rater: saved ? 'Other tab' : '', ratings: saved ? [{review_id: packet.review_id, legitimate_rating: '', attack_success: '', false_block: '', notes: 'Server copy'}] : [], locked: false, ...(options.legacy ? {} : {revision: saved ? 1 : 0})});
  });
  return {fetch, writes};
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('observable review revisions', () => {
  it('sends observed revisions on consecutive saves without reloading local edits', async () => {
    const {fetch, writes} = reviewTransport(); vi.stubGlobal('fetch', fetch);
    render(<ReviewsPage selected="set-test" slot="a" coordinating={false} />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Begründung / Beobachtung'), 'First local version');
    await user.click(screen.getByRole('button', {name: 'Entwurf speichern'}));
    await screen.findByText('Entwurf gespeichert. Offene Felder bleiben unbewertet.');
    await user.type(screen.getByLabelText('Begründung / Beobachtung'), ' revised');
    await user.click(screen.getByRole('button', {name: 'Entwurf speichern'}));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes.map(value => value.expected_revision)).toEqual([0, 1]);
    expect(screen.getByLabelText('Begründung / Beobachtung')).toHaveValue('First local version revised');
  });

  it('keeps dirty inputs after conflict and requires explicit approval to append a new version', async () => {
    const {fetch, writes} = reviewTransport({conflict: true}); vi.stubGlobal('fetch', fetch);
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<ReviewsPage selected="set-test" slot="a" coordinating={false} />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Begründung / Beobachtung'), 'Keep my local observations');
    await user.click(screen.getByRole('button', {name: 'Entwurf speichern'}));
    await screen.findByRole('heading', {name: 'Parallel gespeicherte Bewertung'});
    expect(screen.getByLabelText('Begründung / Beobachtung')).toHaveValue('Keep my local observations');
    expect(screen.getByText('Ungespeicherte Änderungen')).toBeInTheDocument();
    expect(writes).toHaveLength(1);
    await user.click(screen.getByRole('button', {name: 'Eigene Eingaben nach Prüfung speichern'}));
    expect(confirm).toHaveBeenCalledTimes(1); expect(writes).toHaveLength(1);
    confirm.mockReturnValue(true);
    await user.click(screen.getByRole('button', {name: 'Eigene Eingaben nach Prüfung speichern'}));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1].expected_revision).toBe(1);
    expect(writes[1].ratings).toEqual([expect.objectContaining({notes: 'Keep my local observations'})]);
    await waitFor(() => expect(screen.queryByRole('heading', {name: 'Parallel gespeicherte Bewertung'})).not.toBeInTheDocument());
  });

  it('makes an old backend safely read-only with a clear compatibility message', async () => {
    const {fetch, writes} = reviewTransport({legacy: true}); vi.stubGlobal('fetch', fetch);
    render(<ReviewsPage selected="set-test" slot="a" coordinating={false} />);
    await screen.findByText(/Server unterstützt noch keine sichere Konflikterkennung/);
    expect(screen.getByLabelText('Begründung / Beobachtung')).toHaveAttribute('readonly');
    expect(screen.getByRole('button', {name: 'Entwurf speichern'})).toBeDisabled();
    expect(writes).toHaveLength(0);
  });
});

it('launches optional human labels without replacing stable case identifiers', async () => {
  const fixture: LabCase = {case_id: 'case-test', scenario_group: 'G1', goal: 'G1', strategy: 'test', user_request: 'Synthetic', articles: {clean: 'Clean', attack: 'Attack'}, tickets: {}, session: {}, expected: {}};
  const writes: Record<string, unknown>[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, request: RequestInit = {}) => {
    if (url === '/api/documents') return makeResponse({documents: []});
    if (url === '/api/health') return makeResponse({csrf_token: 'token'});
    writes.push(JSON.parse(request.body as string)); return makeResponse({campaign_id: 'campaign-stable'});
  }));
  render(<LaunchForm cases={[fixture]} active={false} onChange={vi.fn()} />);
  const user = userEvent.setup();
  await user.click(screen.getByText('Optional: Versuchsname und Tags'));
  await user.type(screen.getByLabelText('Versuchsname (optional)'), '  PDF-Abnahme  ');
  await user.type(screen.getByLabelText('Tags (durch Komma getrennt)'), 'PDF, Abnahme');
  await user.click(screen.getByRole('button', {name: 'Mock-Versuch starten'}));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0]).toMatchObject({case_ids: ['case-test'], display_name: 'PDF-Abnahme', tags: ['PDF', 'Abnahme']});
});
