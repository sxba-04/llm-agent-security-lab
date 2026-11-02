import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { ComparePage } from './Compare';
import { DocumentsPage } from './Documents';
import type { Campaign } from './types';

const campaign: Campaign = {
  campaign_id: 'synthetic-comparison', created_at: '2026-11-02T00:00:00Z', state: 'completed',
  completed_runs: 4, planned_runs: 4, engineering_only: true,
};

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('distinguishes pending paired evidence from zero and preserves signed differences', async () => {
  const comparisons = [null, 0, 12.5, -12.5].map((difference, index) => ({
    left_variant: 'P', right_variant: 'B', source: 'attack', goal: `G${index + 1}`,
    model: 'fixture', engineering_only: true, n_common_valid_blocks: 1,
    n_candidate_blocks: 1, n_excluded_blocks: 0, excluded: {}, excluded_blocks: [],
    metrics: { backend_violation: {
      left_numerator: 0, right_numerator: 0, denominator: difference === null ? 0 : 1,
      pending: difference === null ? 1 : 0, not_applicable: 0, difference_pp: difference,
    } },
  }));
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith('/summary')
      ? { n_runs: 4, groups: [], paired_comparisons: { comparisons, case_profiles: [] } }
      : { review_sets: [] },
  ), { headers: { 'Content-Type': 'application/json' } })));
  const { container } = render(<ComparePage campaigns={[campaign]} selected={campaign.campaign_id} />);
  await screen.findByText('Keine auswertbaren Paare');
  const cards = container.querySelectorAll('.pair-card');
  const values = Array.from(cards, card => card.querySelector('.pair-difference')?.firstChild?.textContent);
  expect(values).toEqual(['Offen', '0', '+12,5', '-12,5']);
  expect(within(cards[0] as HTMLElement).getByText('1 offen')).toBeInTheDocument();
  expect(within(cards[1] as HTMLElement).getByText('0 offen')).toBeInTheDocument();
  expect(screen.getByText('Keine passenden Ergebnisse')).toBeInTheDocument();
});

it('keeps an all-damaged campaign list outside comparison data requests', async () => {
  const fetch = vi.fn(async (_url: string) => new Response(JSON.stringify({ review_sets: [] }), {
    headers: { 'Content-Type': 'application/json' },
  }));
  vi.stubGlobal('fetch', fetch);
  render(<ComparePage campaigns={[{ ...campaign, valid_evidence: false }]} selected={campaign.campaign_id} />);
  expect(screen.getByText('Keine prüfbaren Versuche zum Vergleich')).toBeInTheDocument();
  expect(screen.queryByLabelText('Messgröße')).not.toBeInTheDocument();
  expect(fetch.mock.calls.every(([url]) => !String(url).includes('/summary'))).toBe(true);
});

it('shows damaged source evidence without offering confirmation or a usable source', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ documents: [
    { document_id: 'damaged-only', valid_evidence: false, error: 'Original fehlt.' },
  ] }), { headers: { 'Content-Type': 'application/json' } })));
  render(<DocumentsPage cases={[]} />);
  expect(screen.getByRole('status')).toHaveTextContent('Daten werden geladen');
  await screen.findByText('Keine prüfbaren PDF-Quellen vorhanden');
  expect(screen.getByText('damaged-only')).toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('Original fehlt.');
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Extraktion bestätigen' })).not.toBeInTheDocument();
});
