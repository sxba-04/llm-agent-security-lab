import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { StorageNotice } from './StorageNotice';

afterEach(cleanup);

it('shows a concrete low-space warning without starting work or deleting evidence', () => {
  render(<StorageNotice storage={{ state: 'low', free_bytes: 50 * 1024 * 1024, total_bytes: 1024 ** 3 }} />);
  expect(screen.getByRole('status', { name: 'Speicherwarnung' })).toHaveTextContent('50 MiB');
  expect(screen.getByRole('status')).toHaveTextContent('Sichere den Forschungsbestand extern');
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

it('does not claim a measured value when free space is unavailable', () => {
  render(<StorageNotice storage={{ state: 'low', free_bytes: null, total_bytes: null }} />);
  expect(screen.getByRole('status')).not.toHaveTextContent('MiB');
});

it('keeps healthy, unknown and older backends free of warning noise', () => {
  const { rerender } = render(<StorageNotice storage={undefined} />);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  rerender(<StorageNotice storage={{ state: 'unknown', free_bytes: null, total_bytes: null }} />);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  rerender(<StorageNotice storage={{ state: 'ok', free_bytes: 1024 ** 3, total_bytes: 1024 ** 4 }} />);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
