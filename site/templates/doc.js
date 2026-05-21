// Shared ASCII bg + markdown renderer for alpi doc subpages
(function(){
  const root = document.documentElement;
  const buttons = document.querySelectorAll('.bg-ctrl button[data-theme]');
  const metaTheme = document.querySelector('meta[name="theme-color"]');

  function readTheme(){
    try { return sessionStorage.getItem('alpi-theme'); }
    catch { return null; }
  }
  function writeTheme(theme){
    try { sessionStorage.setItem('alpi-theme', theme); }
    catch {}
  }
  function setTheme(theme){
    root.dataset.theme = theme;
    writeTheme(theme);
    buttons.forEach(button => button.classList.toggle('on', button.dataset.theme === theme));
    if (metaTheme) metaTheme.setAttribute('content', theme === 'light' ? '#f5f4ef' : '#0a0a0a');
  }

  buttons.forEach(button => {
    button.addEventListener('click', () => setTheme(button.dataset.theme));
  });
  setTheme(readTheme() === 'light' ? 'light' : 'dark');
})();

// Pre-based ASCII background, same engine the landing uses. Lives on top of
// `<div id="ascii-bg"><pre id="ascii-pre"></pre></div>` markup. Color is
// driven by `var(--dim)` so it tracks theme + reads consistently across
// light and dark.
(function(){
  const pre = document.getElementById('ascii-pre');
  if (!pre) return;
  let cols = 0, rows = 0, charW = 7.2, charH = 12;
  let t = 0;
  let running = true;
  const chars = " ·⋅∙•◦◌◍⚬○◎◉+*-~=/\\|".split('');

  function measure(){
    const canary = document.createElement('span');
    canary.style.cssText = 'visibility:hidden;position:absolute;font-family:"JetBrains Mono",monospace;font-size:12px;line-height:12px;white-space:pre;';
    canary.textContent = 'M'.repeat(100);
    document.body.appendChild(canary);
    charW = canary.getBoundingClientRect().width / 100;
    charH = 12;
    canary.remove();
    cols = Math.ceil(window.innerWidth / charW) + 2;
    rows = Math.ceil(window.innerHeight / charH) + 2;
  }

  function renderFlow(){
    const buf = new Array(rows);
    for (let y = 0; y < rows; y++){
      let line = '';
      for (let x = 0; x < cols; x++){
        const nx = x * 0.06;
        const ny = y * 0.11;
        const v =
            Math.sin(nx + t*0.008) +
            Math.cos(ny*1.3 - t*0.005) +
            Math.sin((nx+ny)*0.7 + t*0.012) +
            Math.cos(Math.sqrt(nx*nx + ny*ny)*0.9 - t*0.01);
        const norm = (v + 4) / 8;
        const idx = Math.max(0, Math.min(chars.length-1, Math.floor(norm * chars.length)));
        line += chars[idx];
      }
      buf[y] = line;
    }
    return buf.join('\n');
  }

  let raf;
  function loop(){
    if (!running) return;
    t += 1;
    pre.textContent = renderFlow();
    raf = requestAnimationFrame(loop);
  }
  function start(){
    cancelAnimationFrame(raf);
    running = true;
    measure();
    loop();
  }
  function stop(){
    running = false;
    cancelAnimationFrame(raf);
  }

  let resizeT;
  window.addEventListener('resize', () => {
    clearTimeout(resizeT);
    resizeT = setTimeout(measure, 150);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop(); else start();
  });

  start();
})();

async function renderDoc(file){
  const target = document.getElementById('md-target');
  try {
    const r = await fetch(file);
    if (!r.ok) throw new Error('fetch ' + r.status);
    let md = await r.text();
    // Hide the first h1 if it duplicates the page title — header already shows it
    md = md.replace(/^#\s+.+\n+/, '');
    target.innerHTML = marked.parse(md, { breaks: false, gfm: true });
  } catch (e) {
    target.innerHTML = '<p style="color:#f2f2f0">Could not load <code>' + file + '</code>. Try opening this page through a local server (file:// blocks fetch).</p><pre style="white-space:pre-wrap">' + String(e) + '</pre>';
  }
}
