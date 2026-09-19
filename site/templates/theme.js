(function(){
  const root = document.documentElement;
  const system = matchMedia('(prefers-color-scheme: dark)');
  let choice = null;
  try { choice = localStorage.getItem('alpi-theme'); } catch {}
  if (choice !== 'light' && choice !== 'dark') choice = null;

  function paint(){
    const theme = choice || (system.matches ? 'dark' : 'light');
    root.dataset.theme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'light' ? '#f6f3ec' : '#0c0b09');
    const button = document.querySelector('.theme-btn');
    if (button) button.setAttribute('aria-label', theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
  }

  paint();
  document.addEventListener('DOMContentLoaded', paint);
  system.addEventListener('change', paint);
  document.addEventListener('click', e => {
    if (!e.target.closest('.theme-btn')) return;
    choice = root.dataset.theme === 'light' ? 'dark' : 'light';
    try { localStorage.setItem('alpi-theme', choice); } catch {}
    paint();
  });
})();
