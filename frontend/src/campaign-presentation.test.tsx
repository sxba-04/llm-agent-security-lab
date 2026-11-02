import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { CampaignsPage, RunDetail } from './Campaigns';
import type { RunRecord } from './types';

const record: RunRecord = {
  run_id: 'synthetic-run', case_id: 'synthetic-case', goal: 'G1', variant: 'B',
  source: 'attack', repetition: 1, status: 'completed', is_mock: true,
  final_text: 'Synthetic presentation fixture; not a research result.', events: [],
  initial_tickets: {}, final_tickets: {}, session: {}, expected: {},
  user_request: 'Synthetic task', article_text: 'Synthetic source', metrics: {},
  duration_seconds: 0, model_calls: 0, tool_calls: 0,
};

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('distinguishes a pending campaign lookup from a missing campaign without loading its evidence', () => {
  const fetch = vi.fn();
  vi.stubGlobal('fetch', fetch);
  const view = render(<CampaignsPage cases={[]} campaigns={[]} selected="missing" showNew={false} loading onChange={vi.fn()} />);
  expect(screen.getByText('Versuch wird geprüft …')).toBeInTheDocument();
  expect(screen.queryByText('Versuch nicht verfügbar')).not.toBeInTheDocument();
  view.rerender(<CampaignsPage cases={[]} campaigns={[]} selected="missing" showNew={false} loading={false} onChange={vi.fn()} />);
  expect(screen.getByText('Versuch nicht verfügbar')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Mock-Versuch starten' })).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it('keeps unknown judgments open and uses opposite success colors for legitimate outcomes and violations', () => {
  const view = render(<RunDetail record={{ ...record, metrics: {
    proposal_violation: false, backend_violation: true, legitimate_success: true, attacker_goal: null,
  } }} />);
  const result = (label: string) => screen.getByText(label).querySelector('.pill');
  expect(result('Unberechtigter Vorschlag')).toHaveTextContent('Nein');
  expect(result('Unberechtigter Vorschlag')).toHaveClass('green');
  expect(result('Unberechtigter Effekt')).toHaveTextContent('Ja');
  expect(result('Unberechtigter Effekt')).toHaveClass('amber');
  expect(result('Legitime Aufgabe erfüllt')).toHaveTextContent('Ja');
  expect(result('Legitime Aufgabe erfüllt')).toHaveClass('green');
  expect(result('Angriffsziel erreicht')).toHaveTextContent('Bewertung offen');
  expect(result('Angriffsziel erreicht')).toHaveClass('neutral');

  view.rerender(<RunDetail record={{ ...record, metrics: { legitimate_success: false } }} />);
  expect(result('Legitime Aufgabe erfüllt')).toHaveTextContent('Nein');
  expect(result('Legitime Aufgabe erfüllt')).toHaveClass('red');
  expect(result('Unberechtigter Effekt')).toHaveTextContent('Bewertung offen');
});

it('preserves explicit decision precedence and separately displays observed effects and unclassified events', () => {
  const events: RunRecord['events'] = [
    { seq: 1, type: 'backend_read', data: { allowed: false } },
    { seq: 2, type: 'backend_write', data: { allowed: true } },
    { seq: 3, type: 'context_exposure', data: {} },
    { seq: 4, type: 'article_loaded', data: {} },
  ];
  const { container } = render(<RunDetail record={{ ...record, events }} />);
  const rows = container.querySelectorAll('.timeline-event');
  expect(rows[0]).toHaveClass('blocked');
  expect(rows[0]).toHaveTextContent('Blockiert');
  expect(rows[0]).not.toHaveTextContent('Beobachteter Effekt');
  expect(rows[1]).toHaveClass('effect');
  expect(rows[1]).toHaveTextContent('Zugelassen');
  expect(rows[2]).toHaveTextContent('Beobachteter Effekt');
  expect(rows[3].querySelector('.pill')).toBeNull();
});
