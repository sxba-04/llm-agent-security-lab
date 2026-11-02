import { afterEach, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { TicketDiff } from './ui';

afterEach(cleanup);

it('preserves valid ticket titles and the previous title fallback', () => {
  const { container } = render(<TicketDiff
    before={{ first: { title: 'Alter Titel' }, removed: { title: 'Vorheriger Titel' } }}
    after={{ first: { title: 'Aktueller Titel' }, untitled: {} }}
  />);
  const summaries = Array.from(container.querySelectorAll('summary'), node => node.textContent);
  expect(summaries).toEqual([
    'firstAktueller TitelVerändert', 'removedVorheriger TitelVerändert', 'untitledTicketVerändert',
  ]);
});

it('shows malformed structured titles as JSON text without coercion or HTML execution', () => {
  const title = { imported: '<img src=x onerror="alert(1)">', details: ['synthetic', 42] };
  const { container } = render(<TicketDiff before={{}} after={{ fixture: { title } }} />);
  expect(container.querySelector('summary')).toHaveTextContent(JSON.stringify(title));
  expect(container).not.toHaveTextContent('[object Object]');
  expect(container.querySelector('img')).toBeNull();
});
