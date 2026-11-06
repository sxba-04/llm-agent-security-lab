import { useEffect, useState } from 'react';
import { Monitor } from 'lucide-react';

export type ThemePreference = 'system' | 'light' | 'dark';
export const themeStorageKey = 'security-lab.theme';
const systemThemeQuery = '(prefers-color-scheme: dark)';

function validPreference(value: string | null): ThemePreference {
  return value === 'light' || value === 'dark' ? value : 'system';
}

function readPreference(): ThemePreference {
  try { return validPreference(localStorage.getItem(themeStorageKey)); }
  catch { return 'system'; }
}

function applyTheme(preference: ThemePreference, darkSystem: boolean) {
  const systemTheme = darkSystem ? 'dark' : 'light';
  document.documentElement.dataset.theme = preference === 'system' ? systemTheme : preference;
}

/** Only a display preference is persisted. Authentication and evidence stay separate. */
export function ThemePicker() {
  const [preference, setPreference] = useState<ThemePreference>(readPreference);
  useEffect(() => {
    const media = window.matchMedia?.(systemThemeQuery);
    const update = () => applyTheme(preference, media?.matches ?? false);
    update();
    media?.addEventListener('change', update);
    return () => media?.removeEventListener('change', update);
  }, [preference]);
  useEffect(() => {
    const update = (event: StorageEvent) => {
      if (event.key === themeStorageKey || event.key === null) setPreference(readPreference());
    };
    window.addEventListener('storage', update);
    return () => window.removeEventListener('storage', update);
  }, []);
  function selectTheme(value: string) {
    const next = validPreference(value);
    setPreference(next);
    try { localStorage.setItem(themeStorageKey, next); }
    catch { /* The current tab still works when browser storage is unavailable. */ }
  }
  return <label className="theme-picker"><Monitor size={16} aria-hidden="true" /><span className="sr-only">Farbschema</span><select value={preference} onChange={event => selectTheme(event.target.value)}><option value="system">System</option><option value="light">Hell</option><option value="dark">Dunkel</option></select></label>;
}
