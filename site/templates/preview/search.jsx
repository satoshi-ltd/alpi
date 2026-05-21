// search.jsx — Find in transcript (⌘F)
// Anchored to the top of the chat scroll area. Highlights matches in the thread,
// lets the user navigate hit-to-hit with ↑/↓ or ↵.

const { useState: useStateF, useEffect: useEffectF, useRef: useRefF } = React;

function SearchBar({ open, onClose, scrollRef }) {
  const [q, setQ] = useStateF('');
  const [matchCount, setMatchCount] = useStateF(0);
  const [activeIdx, setActiveIdx] = useStateF(0);
  const inputRef = useRefF(null);

  useEffectF(() => {
    if (open) {
      setQ('');
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    } else {
      clearHighlights();
    }
  }, [open]);

  // Highlight matches in the scroll container DOM. Re-runs whenever q changes.
  useEffectF(() => {
    if (!open) return;
    if (!q) { clearHighlights(); setMatchCount(0); setActiveIdx(0); return; }
    const root = scrollRef.current;
    if (!root) return;
    clearHighlights();
    const re = new RegExp(escapeRe(q), 'gi');
    const matches = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        // Skip nodes inside the search bar itself, action rows, meta lines
        if (!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        let p = node.parentElement;
        while (p && p !== root) {
          if (p.dataset?.searchSkip === '1') return NodeFilter.FILTER_REJECT;
          p = p.parentElement;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(node => {
      const text = node.nodeValue;
      if (!re.test(text)) return;
      re.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let last = 0;
      let m;
      while ((m = re.exec(text))) {
        if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        const span = document.createElement('mark');
        span.className = '__sr-hit';
        span.textContent = m[0];
        frag.appendChild(span);
        matches.push(span);
        last = m.index + m[0].length;
        if (m[0].length === 0) re.lastIndex++;
      }
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
    setMatchCount(matches.length);
    setActiveIdx(0);
    if (matches[0]) {
      matches[0].classList.add('__sr-active');
      matches[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [q, open]);

  const next = (dir = 1) => {
    if (matchCount === 0) return;
    const hits = document.querySelectorAll('.__sr-hit');
    hits[activeIdx]?.classList.remove('__sr-active');
    const newIdx = (activeIdx + dir + matchCount) % matchCount;
    setActiveIdx(newIdx);
    hits[newIdx]?.classList.add('__sr-active');
    hits[newIdx]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  if (!open) return null;
  return (
    <div data-search-skip="1" style={{
      position: 'absolute', top: 12, right: 32, zIndex: 40,
      background: 'var(--bg-elev)',
      border: '.5px solid var(--line-2)',
      borderRadius: 999,
      boxShadow: 'var(--shadow)',
      padding: '6px 6px 6px 14px',
      display: 'flex', alignItems: 'center', gap: 8,
      animation: 'pop-in .18s var(--ease) both',
    }}>
      <window.I.Search style={{ width: 14, height: 14, color: 'var(--ink-3)' }} />
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); next(e.shiftKey ? -1 : 1); }
          if (e.key === 'Escape') { e.preventDefault(); onClose(); }
        }}
        placeholder="Find in transcript…"
        style={{
          width: 220, border: 0, outline: 0, background: 'transparent',
          font: '13px var(--font-sans)', color: 'var(--ink)',
        }}
      />
      <span className="mono tnum" style={{ fontSize: 11, color: matchCount === 0 && q ? 'var(--c-danger)' : 'var(--ink-3)', minWidth: 40, textAlign: 'right' }}>
        {q ? (matchCount === 0 ? 'no hits' : `${activeIdx + 1}/${matchCount}`) : ''}
      </span>
      <window.Tip text="Previous · ⇧↵" side="r">
        <button className="iconbtn" style={{ width: 26, height: 26 }} onClick={() => next(-1)} disabled={matchCount === 0}>
          <svg viewBox="0 0 16 16" className="icon" style={{ width: 13, height: 13 }}><path d="M4 10l4-4 4 4"/></svg>
        </button>
      </window.Tip>
      <window.Tip text="Next · ↵" side="r">
        <button className="iconbtn" style={{ width: 26, height: 26 }} onClick={() => next(1)} disabled={matchCount === 0}>
          <svg viewBox="0 0 16 16" className="icon" style={{ width: 13, height: 13 }}><path d="M4 6l4 4 4-4"/></svg>
        </button>
      </window.Tip>
      <window.Tip text="Close · esc" side="r">
        <button className="iconbtn" style={{ width: 26, height: 26 }} onClick={onClose}>
          <window.I.X />
        </button>
      </window.Tip>
    </div>
  );
}

function clearHighlights() {
  document.querySelectorAll('mark.__sr-hit').forEach((el) => {
    const text = document.createTextNode(el.textContent);
    el.parentNode?.replaceChild(text, el);
  });
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

window.SearchBar = SearchBar;
