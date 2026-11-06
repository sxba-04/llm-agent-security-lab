// Runs before styles and React to prevent a light flash with a dark preference.
// This key holds a display preference only, never credentials or research data.
(function () {
  let preference = 'system';
  try { preference = localStorage.getItem('security-lab.theme') || 'system'; }
  catch { /* Restricted storage falls back to the system preference. */ }
  const darkSystem = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const explicit = preference === 'light' || preference === 'dark';
  document.documentElement.dataset.theme = explicit ? preference : (darkSystem ? 'dark' : 'light');
}());
