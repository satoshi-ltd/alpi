// Shared ASCII bg + markdown renderer for alpi doc subpages
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
  const NC = chars.length;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let sinA, cosA, sinB, cosB, sinC, cosC, sinD, cosD, out;

  function measure(){
    const canary = document.createElement('span');
    canary.style.cssText = 'visibility:hidden;position:absolute;font-family:"Geist Mono",ui-monospace,monospace;font-size:12px;line-height:12px;white-space:pre;';
    canary.textContent = 'M'.repeat(100);
    document.body.appendChild(canary);
    charW = canary.getBoundingClientRect().width / 100;
    charH = 12;
    canary.remove();
    cols = Math.ceil(window.innerWidth / charW) + 2;
    rows = Math.ceil(window.innerHeight / charH) + 2;
    tabulate();
  }

  // Phases are fixed per cell, so they are tabulated on resize and the frame loop stays
  // pure multiply-add: sin(a+wt) = sin a cos wt + cos a sin wt. Never put trig back in it.
  function tabulate(){
    const n = cols * rows;
    sinA = new Float32Array(cols); cosA = new Float32Array(cols);
    sinB = new Float32Array(rows); cosB = new Float32Array(rows);
    sinC = new Float32Array(n);    cosC = new Float32Array(n);
    sinD = new Float32Array(n);    cosD = new Float32Array(n);
    for (let x = 0; x < cols; x++){ const a = x * 0.06; sinA[x] = Math.sin(a); cosA[x] = Math.cos(a); }
    for (let y = 0; y < rows; y++){ const b = y * 0.11 * 1.3; sinB[y] = Math.sin(b); cosB[y] = Math.cos(b); }
    for (let y = 0; y < rows; y++){
      const ny = y * 0.11;
      for (let x = 0; x < cols; x++){
        const nx = x * 0.06, i = y * cols + x;
        const c = (nx + ny) * 0.7, dd = Math.sqrt(nx * nx + ny * ny) * 0.9;
        sinC[i] = Math.sin(c); cosC[i] = Math.cos(c);
        sinD[i] = Math.sin(dd); cosD[i] = Math.cos(dd);
      }
    }
    out = new Array(rows);
  }

  function renderFlow(){
    const ca = Math.cos(t * 0.008),  sa = Math.sin(t * 0.008);
    const cb = Math.cos(t * -0.005), sb = Math.sin(t * -0.005);
    const cc = Math.cos(t * 0.012),  sc = Math.sin(t * 0.012);
    const cd = Math.cos(t * -0.01),  sd = Math.sin(t * -0.01);
    const row = new Array(cols);
    for (let y = 0; y < rows; y++){
      const base = y * cols, sB = sinB[y], cB = cosB[y];
      for (let x = 0; x < cols; x++){
        const i = base + x;
        const v = (sinA[x] * ca + cosA[x] * sa) + (cB * cb - sB * sb)
                + (sinC[i] * cc + cosC[i] * sc) + (cosD[i] * cd - sinD[i] * sd);
        let idx = ((v + 4) * 0.125 * NC) | 0;
        if (idx < 0) idx = 0; else if (idx >= NC) idx = NC - 1;
        row[x] = chars[idx];
      }
      out[y] = row.join('');
    }
    return out.join('\n');
  }

  const FPS = 20, STEP = 60 / FPS;
  let raf, last = 0;
  function loop(now){
    if (!running) return;
    raf = requestAnimationFrame(loop);
    if (now - last < 1000 / FPS) return;
    last = now;
    t += STEP;
    pre.textContent = renderFlow();
  }
  function start(){
    cancelAnimationFrame(raf);
    running = true;
    measure();
    if (reduced){ pre.textContent = renderFlow(); return; }
    last = 0;
    raf = requestAnimationFrame(loop);
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

/* Scroll-spy for the contents rail. Offsets are cached and only recomputed on
   resize; the scroll handler is rAF-throttled and does no layout reads of its
   own. ~15 headings, so this is a comparison loop, not an observer per node. */
(function(){
  const toc = document.querySelector('.toc');
  if (!toc) return;
  const links = new Map();
  toc.querySelectorAll('a[href^="#"]').forEach(a => links.set(decodeURIComponent(a.getAttribute('href').slice(1)), a));
  const heads = [...document.querySelectorAll('.md h2[id]')].filter(h => links.has(h.id));
  if (!heads.length) return;

  let tops = [];
  const measure = () => { tops = heads.map(h => h.getBoundingClientRect().top + window.scrollY); };

  let current = null;
  function paint(){
    const y = window.scrollY + 120;
    let i = 0;
    while (i + 1 < tops.length && tops[i + 1] <= y) i++;
    // At the document bottom the last heading may never cross the threshold, so pin it there.
    const atEnd = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
    const id = atEnd ? heads[heads.length - 1].id : y < tops[0] ? heads[0].id : heads[i].id;
    if (id === current) return;
    if (current) links.get(current).classList.remove('on');
    links.get(id).classList.add('on');
    current = id;
  }

  let queued = false;
  const onScroll = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; paint(); });
  };

  let resizeT;
  window.addEventListener('resize', () => {
    clearTimeout(resizeT);
    resizeT = setTimeout(() => { measure(); paint(); }, 150);
  });
  window.addEventListener('scroll', onScroll, { passive: true });
  toc.addEventListener('click', e => {
    const a = e.target.closest('a[href^="#"]');
    if (a) requestAnimationFrame(() => requestAnimationFrame(paint));
  });
  measure();
  paint();
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
    target.innerHTML = '<p style="color:var(--fg)">Could not load <code>' + file + '</code>. Try opening this page through a local server (file:// blocks fetch).</p><pre style="white-space:pre-wrap">' + String(e) + '</pre>';
  }
}

