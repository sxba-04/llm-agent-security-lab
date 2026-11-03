import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LaunchForm } from './Campaigns';
import { ComparePage } from './Compare';
import { ReviewsPage } from './Reviews';
import { SourceDiff } from './ui';
import type { Campaign, LabCase, Packet } from './types';

const campaign: Campaign = {
  campaign_id: 'synthetic-campaign', created_at: '2026-11-01T00:00:00Z', state: 'completed',
  completed_runs: 4, planned_runs: 4, engineering_only: true,
};
const labCase: LabCase = {
  case_id: 'synthetic-case', scenario_group: 'synthetic-scenario', goal: 'G1', strategy: 'authority',
  user_request: 'Synthetic test only', articles: { clean: 'Clean fixture', attack: 'Attack fixture' },
  tickets: {}, session: {}, expected: {},
};

beforeEach(() => { window.location.hash = 'overview'; });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('retains each comparison disclosure identity when filtering out another goal', async () => {
  const user = userEvent.setup();
  const metric = { left_numerator: 0, right_numerator: 0, denominator: 1, pending: 0,
    not_applicable: 0, left_rate: 0, right_rate: 0, difference_pp: 0 };
  const pairs = ['G1', 'G2'].map(goal => ({
    comparison: 'P-B', left_variant: 'P', right_variant: 'B', source: 'attack', goal,
    model: 'synthetic-model', engineering_only: true, n_candidate_blocks: 1,
    n_common_valid_blocks: 1, n_excluded_blocks: 0, excluded: {}, excluded_blocks: [],
    metrics: { backend_violation: metric },
  }));
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith('/summary')
      ? { n_runs: 4, engineering_only: true, groups: [], paired_comparisons: { comparisons: pairs, case_profiles: [] } }
      : { review_sets: [] },
  ), { headers: { 'Content-Type': 'application/json' } })));
  const { container } = render(<ComparePage selected={campaign.campaign_id} campaigns={[campaign]} />);
  await screen.findAllByText('1 gemeinsame / 1 mögliche Blöcke');
  const initial = container.querySelectorAll<HTMLDetailsElement>('.pair-card details');
  expect(initial).toHaveLength(2);
  await user.click(initial[0].querySelector('summary')!);
  expect(initial[0].open).toBe(true);
  expect(initial[1].open).toBe(false);
  await user.selectOptions(screen.getByLabelText('Angriffsziel', { exact: true }), 'G2');
  const remaining = container.querySelector<HTMLDetailsElement>('.pair-card details');
  expect(remaining).toBe(initial[1]);
  expect(remaining?.open).toBe(false);
  expect(container.querySelectorAll('.pair-card')).toHaveLength(1);
});

it('exposes the nested case label as the checkbox accessible name and toggles that control', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ documents: [] }), {
    headers: { 'Content-Type': 'application/json' },
  })));
  render(<LaunchForm cases={[labCase]} active={false} onChange={vi.fn()} />);
  const checkbox = screen.getByRole('checkbox', { name: 'synthetic-caseG1 · synthetic-scenario' });
  expect(checkbox).toBeChecked();
  await user.click(screen.getByText('synthetic-case', { exact: true }));
  expect(checkbox).not.toBeChecked();
  expect(screen.getByRole('button', { name: 'Mock-Versuch starten' })).toBeDisabled();
});

it('associates case labels with distinct controls when two launch forms are rendered', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ documents: [] }), {
    headers: { 'Content-Type': 'application/json' },
  })));
  render(<><LaunchForm cases={[labCase]} active={false} onChange={vi.fn()} /><LaunchForm cases={[labCase]} active={false} onChange={vi.fn()} /></>);
  const controls = screen.getAllByRole<HTMLInputElement>('checkbox', { name: 'synthetic-caseG1 · synthetic-scenario' });
  expect(controls[0].id).not.toBe(controls[1].id);
  expect(controls[0].labels?.[0].control).toBe(controls[0]);
  expect(controls[1].labels?.[0].control).toBe(controls[1]);
  await user.click(screen.getAllByText('synthetic-case', { exact: true })[1]);
  expect(controls[0]).toBeChecked();
  expect(controls[1]).not.toBeChecked();
});

it('retains source line identity after insertion while preserving duplicate and empty lines', () => {
  const view = render(<SourceDiff clean={'same\nretained\nsame\n'} attack="retained" />);
  const before = [...view.container.querySelectorAll('.source-pane.clean .diff-line')];
  view.rerender(<SourceDiff clean={'inserted\nsame\nretained\nsame\n'} attack="retained" />);
  const after = [...view.container.querySelectorAll('.source-pane.clean .diff-line')];
  expect(after).toHaveLength(5);
  after.slice(1).forEach((line, index) => expect(line).toBe(before[index]));
  expect(after.map(line => line.lastElementChild?.textContent)).toEqual(['inserted', 'same', 'retained', 'same', '\u00a0']);
  expect(after.map(line => line.firstElementChild?.textContent)).toEqual(['1', '2', '3', '4', '5']);
});

it('keeps repeated blocked evidence and does not reuse it across different review packets', async () => {
  const user = userEvent.setup();
  const basePacket: Packet = {
    review_id: 'packet-a', user_request: 'Synthetic request', article_text: 'Synthetic article',
    initial_tickets: {}, final_tickets: {}, session: {}, expected: {}, final_text: 'Synthetic reply',
    status: 'completed', blocked_elements: [{ reason: 'Duplicate' }, { reason: 'Duplicate' }],
    observed_unauthorized_effect: false, rubric: {},
  };
  const packets = [basePacket, { ...basePacket, review_id: 'packet-b' }];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(
    url === '/api/reviews' ? { review_sets: [{ review_set_id: 'set-a', campaign_id: 'synthetic-campaign', packet_count: 2, created_at: '2026-11-03T00:00:00Z' }] }
      : url.endsWith('/packets') ? { packets } : { rater: '', ratings: [], locked: false },
  ), { headers: { 'Content-Type': 'application/json' } })));
  const { container } = render(<ReviewsPage selected="set-a" slot="a" coordinating={false} />);
  await screen.findByText('packet-a');
  const before = [...container.querySelectorAll('.blocked-element')];
  expect(before).toHaveLength(2);
  expect(before.every(element => within(element as HTMLElement).getByText('Duplicate'))).toBe(true);
  await user.click(screen.getByRole('button', { name: 'Weiter' }));
  await screen.findByText('packet-b');
  const after = [...container.querySelectorAll('.blocked-element')];
  expect(after).toHaveLength(2);
  expect(after[0]).not.toBe(before[0]);
  expect(after[1]).not.toBe(before[1]);
  expect(screen.getByLabelText('1. Legitime Aufgabe erfüllt?')).toHaveValue('');
});
