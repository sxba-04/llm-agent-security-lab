import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemePicker, themeStorageKey } from './theme';
import { Disclosure, Tabs } from './ui';
import App from './App';

function mockSystemTheme(initial: boolean) {
  let dark = initial;
  const listeners = new Set<() => void>();
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    get matches() { return dark; },
    addEventListener: (_event: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) => listeners.delete(listener),
  })));
  return (value: boolean) => act(() => { dark = value; listeners.forEach(listener => listener()); });
}

beforeEach(() => { localStorage.clear(); delete document.documentElement.dataset.theme; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); });

describe('display preferences', () => {
  it('follows the system and its changes without persisting unrelated data', () => {
    const changeSystem = mockSystemTheme(true);
    render(<ThemePicker />);
    expect(screen.getByRole('combobox', { name: 'Farbschema' })).toHaveValue('system');
    expect(document.documentElement.dataset.theme).toBe('dark');
    changeSystem(false);
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage).toHaveLength(0);
  });

  it('retains an explicit choice across remounts and ignores system changes until System is chosen', async () => {
    const user = userEvent.setup();
    const changeSystem = mockSystemTheme(false);
    const first = render(<ThemePicker />);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Farbschema' }), 'dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    changeSystem(false);
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage).toHaveLength(1);
    expect(localStorage.getItem(themeStorageKey)).toBe('dark');
    first.unmount();
    render(<ThemePicker />);
    expect(screen.getByRole('combobox', { name: 'Farbschema' })).toHaveValue('dark');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Farbschema' }), 'system');
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('rejects invalid stored values and remains usable when storage is denied', async () => {
    const user = userEvent.setup();
    localStorage.setItem(themeStorageKey, 'unexpected');
    mockSystemTheme(true);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('blocked', 'SecurityError'); });
    render(<ThemePicker />);
    expect(screen.getByRole('combobox', { name: 'Farbschema' })).toHaveValue('system');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Farbschema' }), 'light');
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('falls back safely when reading browser storage is denied', () => {
    mockSystemTheme(true);
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new DOMException('blocked', 'SecurityError'); });
    render(<ThemePicker />);
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('updates another open tab only for the theme preference', () => {
    mockSystemTheme(false);
    render(<ThemePicker />);
    localStorage.setItem(themeStorageKey, 'dark');
    act(() => window.dispatchEvent(new StorageEvent('storage', { key: 'unrelated' })));
    expect(document.documentElement.dataset.theme).toBe('light');
    act(() => window.dispatchEvent(new StorageEvent('storage', { key: themeStorageKey })));
    expect(document.documentElement.dataset.theme).toBe('dark');
  });
});

function TabExample() {
  const [selected, setSelected] = useState('trace');
  return <Tabs label="Laufdetails" items={[{ id: 'trace', label: 'Protokoll' }, { id: 'tickets', label: 'Tickets' }, { id: 'input', label: 'Quelle' }]} selected={selected} onChange={setSelected}><p>{selected}</p></Tabs>;
}

describe('keyboard tabs', () => {
  it('uses one tab stop, arrow keys, Home/End and a named linked panel', async () => {
    const user = userEvent.setup();
    render(<TabExample />);
    const first = screen.getByRole('tab', { name: 'Protokoll' });
    const last = screen.getByRole('tab', { name: 'Quelle' });
    first.focus();
    await user.keyboard('{ArrowLeft}');
    expect(last).toHaveFocus();
    expect(last).toHaveAttribute('aria-selected', 'true');
    expect(first).toHaveAttribute('tabindex', '-1');
    const panel = screen.getByRole('tabpanel', { name: 'Quelle' });
    expect(last).toHaveAttribute('aria-controls', panel.id);
    await user.keyboard('{Home}');
    expect(first).toHaveFocus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Tickets' })).toHaveFocus();
    await user.keyboard('{End}{Tab}');
    expect(screen.getByRole('tabpanel', { name: 'Quelle' })).toHaveFocus();
    await user.click(first);
    expect(screen.getByRole('tabpanel', { name: 'Protokoll' })).toBeInTheDocument();
  });
});

it('keeps a user-expanded disclosure open when saving updates its content', async () => {
  const user = userEvent.setup();
  const { rerender } = render(<Disclosure title="Metadaten bearbeiten"><p>Entwurf</p></Disclosure>);
  await user.click(screen.getByText('Metadaten bearbeiten'));
  await waitFor(() => expect(screen.getByText('Entwurf').closest('details')).toHaveAttribute('open'));
  rerender(<Disclosure title="Metadaten bearbeiten"><p>Gespeichert</p></Disclosure>);
  expect(screen.getByText('Gespeichert').closest('details')).toHaveAttribute('open');
  await user.click(screen.getByText('Metadaten bearbeiten'));
  await waitFor(() => expect(screen.getByText('Gespeichert').closest('details')).not.toHaveAttribute('open'));
  rerender(<Disclosure title="Metadaten bearbeiten"><p>Weiterer Status</p></Disclosure>);
  expect(screen.getByText('Weiterer Status').closest('details')).not.toHaveAttribute('open');
});

describe('mobile navigation', () => {
  function prepareMobile() {
    window.location.hash = 'overview';
    vi.stubGlobal('matchMedia', vi.fn((query: string) => ({ matches: query.includes('max-width'), addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const data = url === '/api/health' ? { version: 'test', mode: 'mock', storage_mode: 'local' }
        : url === '/api/cases' ? { cases: [] } : { campaigns: [] };
      return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
    }));
  }

  it('removes closed navigation from accessibility and restores focus on Escape', async () => {
    prepareMobile();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('heading', { name: 'Sicherheit sichtbar machen.' });
    expect(screen.queryByRole('navigation', { name: 'Hauptnavigation' })).not.toBeInTheDocument();
    const trigger = screen.getByRole('button', { name: 'Menü öffnen' });
    await user.click(trigger);
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' });
    expect(within(nav).getByRole('link', { name: 'Übersicht' })).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(trigger).toHaveFocus();
    expect(document.getElementById('main-navigation')).toHaveAttribute('inert');
    expect(screen.queryByRole('navigation', { name: 'Hauptnavigation' })).not.toBeInTheDocument();
  });

  it('moves focus to the new page only after the main content becomes interactive', async () => {
    prepareMobile();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('heading', { name: 'Sicherheit sichtbar machen.' });
    await user.click(screen.getByRole('button', { name: 'Menü öffnen' }));
    await user.click(within(screen.getByRole('navigation')).getByRole('link', { name: 'Fälle' }));
    await screen.findByRole('heading', { name: 'Der Ausgangspunkt jedes Versuchs.' });
    await waitFor(() => expect(document.getElementById('main-content')).toHaveFocus());
    expect(document.getElementById('main-content')).not.toHaveAttribute('inert');
  });
});
