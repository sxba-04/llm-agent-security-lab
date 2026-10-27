import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReviewsPage } from './Reviews';
import { ComparePage } from './Compare';
import type { Campaign, ReviewSet } from './types';

const restored: ReviewSet = { review_set_id: `review-copy-${'a'.repeat(64)}`, campaign_id: 'legacy-restored', original_campaign_id: 'campaign-original', original_review_set_id: 'review-original', packet_count: 1, created_at: '2026-10-27T13:00:00Z' };
const campaign: Campaign = { campaign_id: restored.campaign_id, created_at: restored.created_at, state: 'completed', completed_runs: 1, planned_runs: 1, engineering_only: true };
function transport() {
  return vi.fn(async (url: string) => {
    const result = url === '/api/reviews' ? { review_sets: [restored], damaged_review_sets: [{ review_set_id: 'review-incomplete', campaign_id: campaign.campaign_id, error: 'Bewertungsbelege unvollständig.' }] }
      : url.endsWith('/packets') ? { packets: [] }
      : url.includes('/ratings/') ? { rater: '', ratings: [], locked: false }
      : url.includes('/summary') ? { n_runs: 1, engineering_only: true, groups: [] }
      : {};
    return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('restored and incomplete review evidence', () => {
  it('reports incomplete sets while a healthy restored set remains selectable and loadable', async () => {
    const fetch = transport(); vi.stubGlobal('fetch', fetch);
    render(<ReviewsPage selected={restored.review_set_id} slot="a" coordinating={false} />);
    await screen.findByText('Bewertungsbelege unvollständig.');
    expect(screen.getByRole('combobox', { name: 'Bewertungssatz' })).toHaveValue(restored.review_set_id);
    expect(screen.queryByRole('option', { name: /review-incomplete/ })).not.toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(`/api/reviews/${restored.review_set_id}/packets`, expect.anything()));
  });

  it('attaches a restored review to its current campaign using the opaque API identifier', async () => {
    const fetch = transport(); vi.stubGlobal('fetch', fetch);
    render(<ComparePage campaigns={[campaign]} selected={campaign.campaign_id} />);
    const choice = await screen.findByRole('option', { name: /Bewertungssatz 1/ });
    await userEvent.setup().selectOptions(screen.getByRole('combobox', { name: 'Menschliche Bewertungen' }), choice);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(`/api/campaigns/${campaign.campaign_id}/summary?review_set_id=${restored.review_set_id}`, expect.anything()));
  });
});
