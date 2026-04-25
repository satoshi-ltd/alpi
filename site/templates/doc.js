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

(function(){
  const canvas = document.getElementById('ascii-bg');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const FONT = 12;
  const CELL_W = FONT * 0.6;
  const CELL_H = FONT * 1.15;
  let cols, rows, t0 = performance.now();

  const CHARS = " ..::--==++**##@";
  function resize(){
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = innerWidth * dpr;
    canvas.height = innerHeight * dpr;
    canvas.style.width = innerWidth + 'px';
    canvas.style.height = innerHeight + 'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
    cols = Math.ceil(innerWidth / CELL_W) + 2;
    rows = Math.ceil(innerHeight / CELL_H) + 2;
  }
  resize();
  addEventListener('resize', resize);

  function cssVar(name, fallback){
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  }

  function frame(ts){
    const t = (ts - t0) / 1000;
    const light = document.documentElement.dataset.theme === 'light';
    const glyph = light ? '70,70,64' : '140,140,134';
    ctx.fillStyle = cssVar('--bg', '#0a0a0a');
    ctx.fillRect(0,0,innerWidth,innerHeight);
    ctx.font = FONT + 'px "JetBrains Mono", monospace';
    ctx.textBaseline = 'top';
    for (let y = 0; y < rows; y++){
      for (let x = 0; x < cols; x++){
        // Flowfield-ish wave
        const nx = x / cols - 0.5;
        const ny = y / rows - 0.5;
        const v = Math.sin(x*0.18 + t*0.5) * 0.5
                + Math.cos(y*0.22 - t*0.3) * 0.5
                + Math.sin((nx*nx + ny*ny)*8 - t*0.6) * 0.5;
        const idx = Math.max(0, Math.min(CHARS.length-1, Math.floor((v*0.5 + 0.5) * CHARS.length)));
        const ch = CHARS[idx];
        if (ch === ' ') continue;
        const a = (v*0.5 + 0.5);
        ctx.fillStyle = `rgba(${glyph},${0.08 + a*0.18})`;
        ctx.fillText(ch, x*CELL_W, y*CELL_H);
      }
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
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
