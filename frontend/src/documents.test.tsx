import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DocumentsPage } from './Documents';
import { LaunchForm } from './Campaigns';
import type { Document, DocumentEntry, LabCase } from './types';

const healthy: Document = { document_id: 'doc-healthy', filename: 'healthy.pdf', sha256: 'original', text_sha256: 'text-hash', page_count: 1, extractor: 'fixture', extracted_text: 'Prüfbarer Text', confirmed: false, valid_evidence: true };
const damaged: DocumentEntry = { document_id: 'doc-damaged', valid_evidence: false, error: 'Die PDF-Belege sind beschädigt oder unvollständig.' };
const fixture: LabCase = { case_id: 'case', scenario_group: 'scenario', goal: 'G1', strategy: 'authority', user_request: 'Auskunft', articles: { clean: 'Fakt', attack: 'Fakt und Angriff' }, tickets: {}, session: {}, expected: {} };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function transport(list: () => DocumentEntry[], confirm?: (url: string) => Document) {
  return vi.fn(async (url: string, options: RequestInit = {}) => {
    const result = url === '/api/documents' ? { documents: list() }
      : url === '/api/health' ? { csrf_token: 'test-token' }
      : options.method === 'POST' && confirm ? confirm(url)
      : {};
    return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
}

describe('damaged PDF evidence', () => {
  it('keeps healthy sources usable and reports damaged sources without offering their text or confirmation', async () => {
    vi.stubGlobal('fetch', transport(() => [damaged, healthy]));
    render(<DocumentsPage cases={[fixture]} />);
    await screen.findByText('Prüfbarer Text');
    expect(screen.getByText('doc-damaged')).toBeInTheDocument();
    expect(screen.getByText(damaged.error)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Extraktion bestätigen' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /doc-damaged/ })).not.toBeInTheDocument();
  });

  it('offers only healthy confirmed sources for a campaign', async () => {
    vi.stubGlobal('fetch', transport(() => [damaged, { ...healthy, confirmed: true }]));
    render(<LaunchForm cases={[fixture]} active={false} onChange={vi.fn()} />);
    await screen.findAllByRole('option', { name: 'healthy.pdf · text-has', hidden: true });
    expect(screen.queryByRole('option', { name: /doc-damaged/, hidden: true })).not.toBeInTheDocument();
  });

  it('does not carry text confirmation over when the selected source becomes damaged and another source is shown', async () => {
    const user = userEvent.setup();
    const second = { ...healthy, document_id: 'doc-second', filename: 'second.pdf', text_sha256: 'other-hash', extracted_text: 'Anderer Text' };
    let changed = false;
    const fetch = transport(() => changed ? [{ ...damaged, document_id: healthy.document_id }, second] : [healthy, second], () => { changed = true; return { ...healthy, confirmed: true }; });
    vi.stubGlobal('fetch', fetch);
    render(<DocumentsPage cases={[fixture]} />);
    await screen.findByText('Prüfbarer Text');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Extraktion bestätigen' }));
    await screen.findByText('Anderer Text');
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Extraktion bestätigen' })).toBeDisabled());
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });
});
