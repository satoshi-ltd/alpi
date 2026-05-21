// panels.jsx — overlay panels:
//   ConnectionPanel  · pick local/remote device
//   Palette          · cmd-K command palette
//   SkillsPanel      · 2-pane skill viewer
//   MemoryPanel      · 2-pane memory file viewer
//   ToolsPanel       · 2-pane tool catalog with parameter table

const { useState: useStateP, useMemo: useMemoP, useRef: useRefP, useEffect: useEffectP } = React;

function Scrim({ onClose, children, align = 'flex-start', top = 96 }) {
  return (
    <div
      className="anim-fade"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: 'absolute', inset: 0,
        background: 'color-mix(in srgb, var(--ink) 20%, transparent)',
        backdropFilter: 'blur(2px)',
        zIndex: 60,
        display: 'flex', alignItems: align, justifyContent: 'center',
        padding: top + 'px 60px 60px',
      }}
    >
      {children}
    </div>
  );
}

function PanelShell({ children, width = 880, maxHeight = '70vh' }) {
  return (
    <div
      className="anim-pop"
      style={{
        width, maxHeight,
        background: 'var(--bg-elev)',
        borderRadius: 14,
        border: '.5px solid var(--line-2)',
        boxShadow: 'var(--shadow)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {children}
    </div>
  );
}

// ── Connection picker ────────────────────────────────────────────────────
function ConnectionPanel({ state, ui }) {
  const [pairing, setPairing] = useStateP('');
  const REMOTES = window.MOCK.REMOTES;

  return (
    <Scrim onClose={() => ui.closePanel()} top={80}>
      <PanelShell width={560} maxHeight="auto">
        <div className="row between" style={{ padding: '14px 18px', borderBottom: '.5px solid var(--line)' }}>
          <div className="row row-gap" style={{ gap: 10 }}>
            <window.I.Globe />
            <span style={{ fontSize: 14, fontWeight: 600 }}>Connection</span>
            <span className="eyebrow" style={{ marginLeft: 4 }}>where alpi runs</span>
          </div>
          <window.Tip text="Close (esc)" side="r">
            <window.Tip text="Close" side="r"><button className="iconbtn" onClick={() => ui.closePanel()}><window.I.X /></button></window.Tip>
          </window.Tip>
        </div>

        <div className="col" style={{ padding: '8px 10px', gap: 1 }}>
          {REMOTES.map(r => {
            const active = state.remote.id === r.id;
            const dotColor =
              r.status === 'connected' ? '#3fb37a' :
              r.status === 'offline'   ? '#c14545' :
                                         '#d4b443';
            return (
              <button
                key={r.id}
                onClick={() => { ui.setRemote(r); ui.closePanel(); }}
                className="row row-gap"
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 10,
                  background: active ? 'var(--selected)' : 'transparent',
                  textAlign: 'left',
                  gap: 12,
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--hover)'; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
              >
                <span style={{
                  width: 28, height: 28, borderRadius: 6,
                  background: 'var(--bg-input)', display: 'grid', placeItems: 'center',
                  border: '.5px solid var(--line)',
                  position: 'relative', flexShrink: 0,
                  color: 'var(--ink-2)',
                }}>
                  {r.isLocal ? <window.I.Cpu /> : <window.I.Wifi />}
                  <span style={{
                    position: 'absolute', right: -2, bottom: -2,
                    width: 9, height: 9, borderRadius: '50%', background: dotColor,
                    border: '2px solid var(--bg-elev)',
                  }} />
                </span>
                <div className="col" style={{ flex: 1, minWidth: 0, gap: 2 }}>
                  <div className="row row-gap" style={{ gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 500 }}>{r.name}</span>
                    {active && <span className="tag">current</span>}
                    {r.status === 'offline' && <span className="tag" style={{ color: '#c14545', background: 'color-mix(in srgb, #c14545 14%, var(--bg-elev))' }}>offline</span>}
                  </div>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{r.host}</span>
                </div>
                {!r.isLocal && (
                  <button
                    onClick={(e) => { e.stopPropagation(); }}
                    style={{ fontSize: 11, color: 'var(--ink-3)', padding: '4px 8px', borderRadius: 6, flexShrink: 0 }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'color-mix(in srgb, #c14545 10%, transparent)'; e.currentTarget.style.color = '#c14545'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--ink-3)'; }}
                  >Forget</button>
                )}
              </button>
            );
          })}
        </div>

        <div style={{
          borderTop: '.5px solid var(--line)',
          padding: '14px 18px',
          background: 'var(--bg-side)',
        }}>
          <div className="row between" style={{ marginBottom: 8 }}>
            <span className="eyebrow">Pair a new device</span>
            <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>
              Paste an <code className="mono" style={{ fontSize: 11 }}>alpi://</code> link from another machine
            </span>
          </div>
          <div className="row row-gap" style={{ gap: 8 }}>
            <input
              className="field field-mono"
              value={pairing}
              onChange={e => setPairing(e.target.value)}
              placeholder="alpi://device?v=2&host=100.64.0.1&port=49200&name=home&token=…"
              style={{ flex: 1 }}
            />
            <button
              className="btn btn-primary"
              disabled={!pairing.startsWith('alpi://')}
              style={{ opacity: pairing.startsWith('alpi://') ? 1 : 0.5 }}
            >Pair</button>
          </div>
        </div>
      </PanelShell>
    </Scrim>
  );
}

// ── Command Palette (Cmd-K) ──────────────────────────────────────────────
function Palette({ state, ui }) {
  const [q, setQ] = useStateP('');
  const [idx, setIdx] = useStateP(1);
  const inputRef = useRefP(null);

  useEffectP(() => { inputRef.current?.focus(); }, []);

  // Context-aware groups: BROWSE (skills/memory/tools) only shows when current view is a profile chat.
  const isProfileContext = state.view === 'chat' && state.activeKind === 'profile';
  const groups = useMemoP(() => buildPaletteGroups({ isProfileContext }), [isProfileContext]);

  const flat = useMemoP(() => {
    const out = [];
    groups.forEach(g => {
      const filtered = q
        ? g.items.filter(it => it.label.toLowerCase().includes(q.toLowerCase()))
        : g.items;
      if (filtered.length) {
        out.push({ kind: 'header', label: g.label });
        filtered.forEach(it => out.push({ kind: 'item', ...it }));
      }
    });
    return out;
  }, [q, groups]);

  const items = flat.filter(x => x.kind === 'item');

  const onKey = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'Tab') {
      e.preventDefault(); setIdx(i => Math.min(items.length - 1, i + 1));
    } else if (e.key === 'ArrowUp' || (e.shiftKey && e.key === 'Tab')) {
      e.preventDefault(); setIdx(i => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault(); run(items[idx]);
    } else if (e.key === 'Escape') {
      ui.closePalette();
    }
  };

  const run = (it) => {
    if (!it) return;
    if (it.kind === 'profile')   ui.openChat({ kind: 'profile', id: it.target });
    else if (it.kind === 'workgroup') ui.openChat({ kind: 'workgroup', id: it.target });
    else if (it.kind === 'overlay')   ui.openPanel(it.target);
    else if (it.kind === 'route') {
      if (it.target === 'settings') ui.setView('settings');
      else if (it.target === 'chat') ui.setView('chat');
      else if (it.target === 'new') ui.setView('new');
    }
    ui.closePalette();
  };

  return (
    <Scrim onClose={() => ui.closePalette()} top={120}>
      <PanelShell width={520} maxHeight="60vh">
        <div style={{ padding: '0 16px', borderBottom: '.5px solid var(--line)' }}>
          <input
            ref={inputRef}
            value={q}
            onChange={e => { setQ(e.target.value); setIdx(0); }}
            onKeyDown={onKey}
            placeholder="Type a command…"
            style={{
              width: '100%', height: 44,
              border: 0, outline: 0, background: 'transparent',
              font: '14px var(--font-sans)', color: 'var(--ink)',
            }}
          />
        </div>
        <div className="scroll" style={{ flex: 1, padding: '6px 6px 10px' }}>
          {flat.length === 0 ? (
            <div className="col center" style={{ padding: '40px 0', color: 'var(--ink-3)', fontSize: 13 }}>
              No matches
            </div>
          ) : (
            flat.map((row) => {
              if (row.kind === 'header') {
                return (
                  <div key={'h-' + row.label} className="eyebrow" style={{ padding: '14px 12px 6px' }}>
                    {row.label}
                  </div>
                );
              }
              const itemIndex = items.findIndex(it => it.id === row.id);
              const selected = itemIndex === idx;
              // Resolve the leading glyph by item kind
              let glyph = null;
              if (row.kind === 'profile') {
                const c = window.MOCK.PROFILES.find(p => p.id === row.target)?.color;
                glyph = <span className="diamond" style={{ '--c': c, width: 9, height: 9 }} />;
              } else if (row.kind === 'workgroup') {
                glyph = <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--ink-3)', fontSize: 13, fontWeight: 500 }}>#</span>;
              } else {
                // View / Browse / Create icons (1.5px stroke, ink-3)
                const ICONS = {
                  'open-settings':   <window.I.Gear />,
                  'find-transcript': <window.I.Search />,
                  'view-tools':      <window.I.Cpu />,
                  'view-skills':     <window.I.Spark />,
                  'view-memory':     <window.I.Folder />,
                  'new-chat':        <window.I.Plus />,
                  'new-profile':     <window.I.Plus />,
                  'new-workgroup':   <window.I.Plus />,
                };
                glyph = <span style={{ color: 'var(--ink-3)', display: 'inline-flex' }}>{ICONS[row.id] || <window.I.ChevRight />}</span>;
              }
              return (
                <button
                  key={row.id}
                  onClick={() => run(row)}
                  onMouseEnter={() => setIdx(itemIndex)}
                  className="row"
                  style={{
                    width: '100%', padding: '7px 12px', borderRadius: 8,
                    background: selected ? 'var(--selected)' : 'transparent',
                    textAlign: 'left', gap: 10, alignItems: 'center',
                  }}
                >
                  <span style={{ width: 16, display: 'inline-flex', justifyContent: 'center', flexShrink: 0 }}>
                    {glyph}
                  </span>
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--ink)' }}>{row.label}</span>
                  {row.shortcut && (
                    <span style={{ display: 'inline-flex', gap: 2 }}>
                      {row.shortcut.split('').map((ch, ci) => (
                        <span key={ci} className="kbd">{ch}</span>
                      ))}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>
      </PanelShell>
    </Scrim>
  );
}

// Builds the palette groups based on current context
function buildPaletteGroups({ isProfileContext }) {
  const PROFILES = window.MOCK.PROFILES;
  const WORKGROUPS = window.MOCK.WORKGROUPS;

  // Top 4 pinned + remaining alpis + workgroups, max 9 with ⌘1..9 shortcuts
  const navigateItems = [];
  const pinned = PROFILES.filter(p => p.pinned);
  const rest = PROFILES.filter(p => !p.pinned).slice(0, 4);
  const wg = WORKGROUPS.slice(0, 1); // architecture
  const order = [...pinned, ...wg, ...rest];
  order.slice(0, 9).forEach((it, i) => {
    const isWg = WORKGROUPS.find(w => w.id === it.id);
    navigateItems.push({
      id: `open-${it.id}`,
      label: isWg ? `Open #${it.id}` : `Open @${it.id}`,
      kind: isWg ? 'workgroup' : 'profile',
      target: it.id,
      shortcut: `⌘${i + 1}`,
    });
  });

  const groups = [
    { label: 'Navigate', items: navigateItems },
    {
      label: 'View',
      items: [
        { id: 'open-settings',    label: 'Open settings',    kind: 'route',   target: 'settings', shortcut: '⌘,' },
        { id: 'find-transcript',  label: 'Find in transcript', kind: 'noop',  shortcut: '⌘F' },
      ],
    },
  ];

  if (isProfileContext) {
    groups.push({
      label: 'Browse',
      items: [
        { id: 'view-tools',  label: 'Tools',  kind: 'overlay', target: 'tools',  shortcut: '⇧⌘T' },
        { id: 'view-skills', label: 'Skills', kind: 'overlay', target: 'skills', shortcut: '⇧⌘S' },
        { id: 'view-memory', label: 'Memory', kind: 'overlay', target: 'memory', shortcut: '⇧⌘M' },
      ],
    });
  }

  groups.push({
    label: 'Create',
    items: [
      { id: 'new-chat',      label: 'New chat',      kind: 'route', target: 'new', shortcut: '⌘N' },
      { id: 'new-profile',   label: 'New profile',   kind: 'noop',                 shortcut: '⇧⌘N' },
      { id: 'new-workgroup', label: 'New workgroup', kind: 'noop',                 shortcut: '⇧⌘W' },
    ],
  });

  return groups;
}

// ── Markdown-lite renderer for skill / memory bodies ─────────────────────
function MdLite({ text }) {
  // headings (## title), code blocks (    indent or ```), bold (**), inline `code`
  const lines = text.split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith('### ')) {
      out.push(<h4 key={i} style={{ margin: '20px 0 6px', fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{l.slice(4)}</h4>);
      i++; continue;
    }
    if (l.startsWith('## ')) {
      out.push(<h3 key={i} style={{ margin: '22px 0 8px', fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{l.slice(3)}</h3>);
      i++; continue;
    }
    if (l.startsWith('# ')) {
      out.push(<h2 key={i} style={{ margin: '8px 0 14px', fontSize: 17, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{l.slice(2)}</h2>);
      i++; continue;
    }
    // table: | a | b | with separator row of dashes
    if (l.trim().startsWith('|') && lines[i+1]?.trim().startsWith('|') && /^[\s|:-]+$/.test(lines[i+1])) {
      const head = l.split('|').slice(1,-1).map(c => c.trim());
      i += 2;
      const rows = [];
      while (lines[i] && lines[i].trim().startsWith('|')) {
        rows.push(lines[i].split('|').slice(1,-1).map(c => c.trim()));
        i++;
      }
      out.push(
        <table key={'tbl-' + i} style={{
          width: '100%', borderCollapse: 'collapse', margin: '12px 0 16px',
          fontFamily: 'var(--font-mono)', fontSize: 12,
        }}>
          <thead>
            <tr>{head.map((h, hi) => <th key={hi} style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--ink-3)', fontWeight: 500, borderBottom: '.5px solid var(--line-2)' }}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => <tr key={ri}>{r.map((c, ci) => <td key={ci} style={{ padding: '6px 10px', borderBottom: '.5px solid var(--line)' }}>{c}</td>)}</tr>)}
          </tbody>
        </table>
      );
      continue;
    }
    // code block: indented
    if (l.startsWith('    ') && !l.trim().match(/^[-*]/)) {
      const block = [];
      while (lines[i]?.startsWith('    ')) { block.push(lines[i].slice(4)); i++; }
      out.push(
        <pre key={'pre-' + i} style={{
          margin: '12px 0', padding: '12px 14px', borderRadius: 8,
          background: 'var(--hover)', border: '.5px solid var(--line)',
          fontFamily: 'var(--font-mono)', fontSize: 12,
          overflowX: 'auto', whiteSpace: 'pre',
        }}>{block.join('\n')}</pre>
      );
      continue;
    }
    // numbered list
    const numMatch = l.match(/^(\d+)\.\s+(.*)$/);
    if (numMatch) {
      const items = [];
      while (lines[i]) {
        const m = lines[i].match(/^(\d+)\.\s+(.*)$/);
        if (!m) break;
        items.push(m[2]);
        i++;
      }
      out.push(
        <ol key={'ol-' + i} style={{ margin: '8px 0', paddingLeft: 22, fontSize: 13, lineHeight: 'var(--lh-normal)' }}>
          {items.map((it, ii) => <li key={ii} style={{ marginBottom: 4 }}>{inlineMd(it)}</li>)}
        </ol>
      );
      continue;
    }
    // bullet list
    if (l.match(/^[-*]\s+/)) {
      const items = [];
      while (lines[i]?.match(/^[-*]\s+/)) {
        items.push(lines[i].replace(/^[-*]\s+/, ''));
        i++;
      }
      out.push(
        <ul key={'ul-' + i} style={{ margin: '8px 0', paddingLeft: 18, fontSize: 13, lineHeight: 'var(--lh-normal)' }}>
          {items.map((it, ii) => <li key={ii} style={{ marginBottom: 4 }}>{inlineMd(it)}</li>)}
        </ul>
      );
      continue;
    }
    if (l.trim() === '') { i++; continue; }
    // paragraph
    const parts = [l];
    while (lines[i+1] && lines[i+1].trim() !== '' && !lines[i+1].match(/^([#-*]|\d+\.)\s/) && !lines[i+1].startsWith('|') && !lines[i+1].startsWith('    ')) {
      parts.push(lines[i+1]); i++;
    }
    out.push(<p key={'p-' + i} style={{ margin: '8px 0', fontSize: 13, lineHeight: 1.6, textWrap: 'pretty' }}>{inlineMd(parts.join(' '))}</p>);
    i++;
  }
  return <>{out}</>;
}

function inlineMd(s) {
  // **bold**, `code`
  const parts = s.split(/(\*\*[^*]+\*\*|`[^`]+`)/);
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**'))
      return <strong key={i} style={{ fontWeight: 600 }}>{p.slice(2, -2)}</strong>;
    if (p.startsWith('`') && p.endsWith('`'))
      return <code key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: '.92em', background: 'var(--hover)', padding: '1px 5px', borderRadius: 4 }}>{p.slice(1, -1)}</code>;
    return <React.Fragment key={i}>{p}</React.Fragment>;
  });
}

// ── Two-pane viewer (Skills / Memory / Tools share this scaffold) ────────
function TwoPanePanel({ title, count, items, renderListItem, renderDetail, onClose, searchPlaceholder, accent }) {
  const [q, setQ] = useStateP('');
  const [pickedId, setPickedId] = useStateP(items[0]?.id);

  const filtered = useMemoP(() => {
    if (!q) return items;
    return items.filter(it => (it.id + ' ' + (it.group || '') + ' ' + (it.blurb || it.desc || '')).toLowerCase().includes(q.toLowerCase()));
  }, [q, items]);

  const picked = items.find(it => it.id === pickedId) || filtered[0];

  return (
    <Scrim onClose={onClose} top={60}>
      <PanelShell width={1080} maxHeight="80vh">
        <div className="row between" style={{
          padding: '12px 18px', borderBottom: '.5px solid var(--line)',
        }}>
          <div className="row row-gap" style={{ gap: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 600, textTransform: 'capitalize' }}>{title}</span>
            <span className="tag">{count}</span>
            <span className="eyebrow" style={{ marginLeft: 4 }}>
              {title === 'skills' && '· instructions the agent loads on demand'}
              {title === 'memory' && '· files read on every turn'}
              {title === 'tools' && '· native callable functions'}
            </span>
          </div>
          <div className="row row-gap" style={{ gap: 6 }}>
            <window.Tip text="Close" side="r"><button className="iconbtn" onClick={onClose}><window.I.X /></button></window.Tip>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', flex: 1, minHeight: 0 }}>
          <div className="col" style={{ borderRight: '.5px solid var(--line)', background: 'var(--bg-side)', minHeight: 0 }}>
            <div style={{ padding: '10px 12px 6px' }}>
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder={searchPlaceholder || `Search ${title}…`}
                className="field"
                style={{ height: 30, padding: '0 10px', fontSize: 12 }}
              />
            </div>
            <div className="scroll" style={{ flex: 1, padding: '4px 8px 12px' }}>
              {filtered.map(it => renderListItem(it, pickedId === it.id, () => setPickedId(it.id)))}
              {filtered.length === 0 && (
                <div className="col center" style={{ padding: '24px 0', color: 'var(--ink-3)', fontSize: 12 }}>
                  No matches
                </div>
              )}
            </div>
          </div>
          <div className="scroll" style={{ minHeight: 0, padding: '20px 26px' }}>
            {picked ? renderDetail(picked) : (
              <div className="col center" style={{ padding: '60px 0', color: 'var(--ink-3)' }}>
                Pick something on the left
              </div>
            )}
          </div>
        </div>
      </PanelShell>
    </Scrim>
  );
}

// ── Skills viewer ────────────────────────────────────────────────────────
function SkillsPanel({ state, ui }) {
  const items = window.MOCK.SKILLS;
  return (
    <TwoPanePanel
      title="skills"
      count={items.length}
      items={items}
      searchPlaceholder="Search skills…"
      onClose={() => ui.closePanel()}
      renderListItem={(it, sel, onClick) => (
        <button
          key={it.id}
          onClick={onClick}
          className="col"
          style={{
            width:'100%', padding: '8px 10px', borderRadius: 8,
            background: sel ? 'var(--selected)' : 'transparent',
            textAlign: 'left', gap: 2,
          }}
          onMouseEnter={e => { if (!sel) e.currentTarget.style.background = 'var(--hover)'; }}
          onMouseLeave={e => { if (!sel) e.currentTarget.style.background = 'transparent'; }}
        >
          <div className="row" style={{ width: '100%', gap: 6 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500 }}>{it.id}</span>
            <span className="tag" style={{ marginLeft: 'auto', fontSize: 11 }}>{it.size}</span>
          </div>
          <span style={{ fontSize: 11, color: 'var(--ink-3)', lineHeight: 1.4, textWrap: 'pretty', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{it.blurb}</span>
        </button>
      )}
      renderDetail={(it) => (
        <div className="col" style={{ gap: 14 }}>
          <div className="row between" style={{ alignItems: 'baseline' }}>
            <div className="col" style={{ gap: 4 }}>
              <h2 style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 600 }}>{it.id}</h2>
              <span style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 'var(--lh-normal)', maxWidth: 640 }}>{it.blurb}</span>
            </div>
            <div className="row row-gap" style={{ gap: 6 }}>
              <button className="btn btn-ghost"><window.I.Play /><span>Run</span></button>
              <button className="btn btn-ghost"><window.I.Eye /><span>Edit</span></button>
            </div>
          </div>
          <div className="mono" style={{
            fontSize: 11, color: 'var(--ink-3)', padding: '6px 10px',
            background: 'var(--hover)', borderRadius: 6, border: '.5px solid var(--line)',
            wordBreak: 'break-all',
          }}>{it.path}</div>
          <div style={{ borderTop: '.5px solid var(--line)', paddingTop: 4 }} />
          <MdLite text={it.body} />
        </div>
      )}
    />
  );
}

// ── Memory viewer ────────────────────────────────────────────────────────
function MemoryPanel({ state, ui }) {
  const items = window.MOCK.MEMORY_FILES;
  return (
    <TwoPanePanel
      title="memory"
      count={items.length}
      items={items}
      searchPlaceholder="Search memory…"
      onClose={() => ui.closePanel()}
      renderListItem={(it, sel, onClick) => (
        <button
          key={it.id}
          onClick={onClick}
          className="row row-gap"
          style={{
            width:'100%', padding: '8px 10px', borderRadius: 8,
            background: sel ? 'var(--selected)' : 'transparent',
            textAlign: 'left', gap: 8,
          }}
          onMouseEnter={e => { if (!sel) e.currentTarget.style.background = 'var(--hover)'; }}
          onMouseLeave={e => { if (!sel) e.currentTarget.style.background = 'transparent'; }}
        >
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500, flex: 1 }}>{it.id}</span>
          <span className="tag" style={{ fontSize: 11 }}>{it.size}</span>
        </button>
      )}
      renderDetail={(it) => (
        <div className="col" style={{ gap: 14 }}>
          <div className="row between" style={{ alignItems: 'baseline' }}>
            <h2 style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 600 }}>{it.id}</h2>
            <div className="row row-gap" style={{ gap: 6 }}>
              <span className="tag">{it.size}</span>
              <button className="btn btn-ghost"><window.I.Eye /><span>Edit</span></button>
            </div>
          </div>
          <MdLite text={it.body} />
        </div>
      )}
    />
  );
}

// ── Tools viewer ─────────────────────────────────────────────────────────
function ToolsPanel({ state, ui }) {
  const tools = window.MOCK.TOOLS;
  const grouped = useMemoP(() => {
    const m = {};
    tools.forEach(t => { (m[t.group] ||= []).push(t); });
    return m;
  }, [tools]);

  const [q, setQ] = useStateP('');
  const [pickedId, setPickedId] = useStateP(tools[0]?.id);
  const filtered = useMemoP(() => {
    if (!q) return tools;
    return tools.filter(t => (t.id + ' ' + t.group + ' ' + t.desc).toLowerCase().includes(q.toLowerCase()));
  }, [q]);
  const filteredGrouped = useMemoP(() => {
    const m = {};
    filtered.forEach(t => { (m[t.group] ||= []).push(t); });
    return m;
  }, [filtered]);

  const picked = tools.find(t => t.id === pickedId) || filtered[0];

  return (
    <Scrim onClose={() => ui.closePanel()} top={60}>
      <PanelShell width={1080} maxHeight="80vh">
        <div className="row between" style={{
          padding: '12px 18px', borderBottom: '.5px solid var(--line)',
        }}>
          <div className="row row-gap" style={{ gap: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Tools</span>
            <span className="tag">{tools.length}</span>
            <span className="eyebrow" style={{ marginLeft: 4 }}>· native callable functions</span>
          </div>
          <div className="row row-gap" style={{ gap: 6 }}>
            <window.Tip text="Close" side="r"><button className="iconbtn" onClick={() => ui.closePanel()}><window.I.X /></button></window.Tip>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', flex: 1, minHeight: 0 }}>
          <div className="col" style={{ borderRight: '.5px solid var(--line)', background: 'var(--bg-side)', minHeight: 0 }}>
            <div style={{ padding: '10px 12px 6px' }}>
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search tools…"
                className="field"
                style={{ height: 30, padding: '0 10px', fontSize: 12 }}
              />
            </div>
            <div className="scroll" style={{ flex: 1, padding: '4px 8px 12px' }}>
              {Object.keys(filteredGrouped).map(g => (
                <div key={g}>
                  <div className="eyebrow" style={{ padding: '12px 10px 4px' }}>{g}</div>
                  {filteredGrouped[g].map(t => {
                    const sel = pickedId === t.id;
                    return (
                      <button
                        key={t.id}
                        onClick={() => setPickedId(t.id)}
                        className="row row-gap"
                        style={{
                          width: '100%', padding: '6px 10px', borderRadius: 8,
                          background: sel ? 'var(--selected)' : 'transparent',
                          textAlign: 'left', gap: 8,
                        }}
                        onMouseEnter={e => { if (!sel) e.currentTarget.style.background = 'var(--hover)'; }}
                        onMouseLeave={e => { if (!sel) e.currentTarget.style.background = 'transparent'; }}
                      >
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, flex: 1 }}>{t.id}</span>
                        <span style={{ fontSize: 11, color: 'var(--ink-4)' }}>{t.params.length}</span>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
          <div className="scroll" style={{ minHeight: 0, padding: '20px 26px' }}>
            {picked && (
              <div className="col" style={{ gap: 14 }}>
                <div className="row" style={{ gap: 10, alignItems: 'baseline' }}>
                  <h2 style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 600 }}>{picked.id}</h2>
                  <span className="tag">{picked.group}</span>
                </div>
                <p style={{ margin: 0, fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.6, textWrap: 'pretty', maxWidth: 680, whiteSpace: 'pre-wrap' }}>
                  {picked.desc}
                </p>
                {picked.params.length > 0 ? (
                  <div style={{ marginTop: 6 }}>
                    <div className="eyebrow" style={{ marginBottom: 6 }}>Parameters</div>
                    <table style={{
                      width: '100%', borderCollapse: 'collapse',
                      fontFamily: 'var(--font-mono)', fontSize: 12,
                    }}>
                      <thead>
                        <tr>
                          {['parameter','type','required','default'].map(h => (
                            <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--ink-3)', fontWeight: 500, borderBottom: '.5px solid var(--line-2)', textTransform: 'uppercase', fontSize: 11, letterSpacing: '.05em' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {picked.params.map(p => (
                          <tr key={p.name}>
                            <td style={{ padding: '8px 12px', borderBottom: '.5px solid var(--line)' }}>{p.name}</td>
                            <td style={{ padding: '8px 12px', borderBottom: '.5px solid var(--line)', color: 'var(--ink-2)' }}>{p.type}</td>
                            <td style={{ padding: '8px 12px', borderBottom: '.5px solid var(--line)', color: p.req ? 'var(--ink)' : 'var(--ink-3)' }}>{p.req ? 'yes' : 'no'}</td>
                            <td style={{ padding: '8px 12px', borderBottom: '.5px solid var(--line)', color: 'var(--ink-3)' }}>{p.default || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>No parameters.</div>
                )}
              </div>
            )}
          </div>
        </div>
      </PanelShell>
    </Scrim>
  );
}

window.ConnectionPanel = ConnectionPanel;
window.Palette = Palette;
window.SkillsPanel = SkillsPanel;
window.MemoryPanel = MemoryPanel;
window.ToolsPanel = ToolsPanel;
