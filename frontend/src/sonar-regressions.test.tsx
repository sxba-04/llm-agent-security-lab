import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LaunchForm } from './Campaigns';
import { ComparePage } from './Compare';
import type { Campaign, LabCase } from './types';

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
