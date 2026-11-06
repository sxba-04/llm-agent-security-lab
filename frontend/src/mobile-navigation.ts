import { useEffect, useRef, useState } from 'react';

function trapTab(event: KeyboardEvent, sidebar: HTMLElement | null) {
  if (event.key !== 'Tab') return;
  const items = sidebar?.querySelectorAll<HTMLElement>('a[href],button:not(:disabled),select:not(:disabled)');
  if (!items?.length) return;
  const first = items[0], last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

/** Match the CSS breakpoint and keep focus inside the temporary mobile drawer. */
export function useMobileNavigation(currentLabel: string) {
  const [menu, setMenu] = useState(false);
  const [mobile, setMobile] = useState(() => window.matchMedia?.('(max-width: 760px)').matches ?? false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const wasMobileMenu = useRef(false);
  const focusMainAfterClose = useRef(false);
  useEffect(() => {
    const media = window.matchMedia?.('(max-width: 760px)');
    const update = () => { setMobile(media?.matches ?? false); if (!media?.matches) setMenu(false); };
    media?.addEventListener('change', update);
    return () => media?.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    setMenu(false); document.title = `${currentLabel} · Agent Security Lab`;
    if (wasMobileMenu.current) focusMainAfterClose.current = true;
  }, [currentLabel]);
  useEffect(() => {
    wasMobileMenu.current = mobile && menu;
    if (!menu && focusMainAfterClose.current) {
      focusMainAfterClose.current = false;
      document.getElementById('main-content')?.focus();
    }
    if (!mobile || !menu) return;
    sidebar.current?.querySelector<HTMLElement>('[aria-current="page"]')?.focus();
    const closeOrTrap = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault(); setMenu(false); menuButton.current?.focus(); return;
      }
      trapTab(event, sidebar.current);
    };
    document.addEventListener('keydown', closeOrTrap);
    return () => document.removeEventListener('keydown', closeOrTrap);
  }, [mobile, menu]);
  function closeMenu() { setMenu(false); menuButton.current?.focus(); }
  function selectCurrentPage() {
    if (mobile) { focusMainAfterClose.current = true; setMenu(false); }
  }
  return { menu, mobile, menuButton, sidebar, closeMenu, selectCurrentPage, toggleMenu: () => setMenu(value => !value) };
}
