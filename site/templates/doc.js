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


(function(){
  document.querySelectorAll('.md pre').forEach(pre => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'copy';
    button.textContent = 'copy';
    button.setAttribute('aria-label', 'Copy code');
    button.addEventListener('click', async () => {
      const code = pre.querySelector('code') || pre;
      try {
        await navigator.clipboard.writeText(code.innerText.replace(/\n$/, ''));
        button.textContent = 'copied';
      } catch {
        button.textContent = 'press ⌘C';
      }
      setTimeout(() => { button.textContent = 'copy'; }, 1600);
    });
    pre.appendChild(button);
  });
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

