// sidebar.jsx — left rail. Connection picker, profile list (pinned + all), workgroups.
// Replaces the original dropdown with a clean cell + opens a side panel.

const { useState, useMemo } = React;

function ConnectionCell({ remote, onOpenPicker, offline }) {
  const status = offline ? 'offline' : remote.status;
  return (
    <window.Tip text={offline ? 'Daemon offline — click to retry' : 'Switch connection'} side="l" block>
      <button className="conn-pill" onClick={onOpenPicker}>
        <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', flexShrink: 0, color: 'var(--ink-2)' }}>
          {remote.isLocal
            ? <window.I.Cpu />
            : <window.I.Wifi />
          }
          <span style={{
            position: 'absolute', right: -2, bottom: -2,
            width: 7, height: 7, borderRadius: '50%',
            background: status === 'connected' ? '#3fb37a' : status === 'offline' ? '#c14545' : '#d4b443',
            border: '1.5px solid var(--bg-elev)',
            animation: status === 'offline' ? 'pulse-dot 1.4s ease-in-out infinite' : 'none',
          }} />
        </span>
        <span className="col" style={{ justifyContent: 'center', flex: 1, minWidth: 0, gap: 0, textAlign: 'left' }}>
          <span className="name" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>
            {remote.isLocal ? 'Local' : remote.name.split('.')[0]}
          </span>
          <span className="host" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', color: status === 'offline' ? 'var(--c-danger)' : 'var(--ink-3)' }}>
            {status === 'offline' ? 'offline · retrying…' : remote.host}
          </span>
        </span>
        <window.I.ChevDown style={{ flexShrink: 0, color: 'var(--ink-3)' }} />
      </button>
    </window.Tip>
  );
}

function ProfileRow({ p, active, onClick, density, dir, showColorWash, hideTs, onContextMenu, onPinToggle }) {
  const isSelected = active;
  const tinted = showColorWash && isSelected;
  const [hover, setHover] = useState(false);
  const needsProvider = !p.model;
  // Visual hierarchy:
  //   unread   → 600 / ink           (top urgency)
  //   selected → 500 / ink           (current context)
  //   default  → 400 / ink-2         (passive list — feels airy)
  //   needs-provider → 400 / ink-3   (incomplete — muted)
  const nameWeight = p.unread ? 600 : (isSelected || tinted ? 500 : 400);
  const nameColor  = p.unread || isSelected || tinted ? 'var(--ink)'
                   : needsProvider ? 'var(--ink-3)'
                   : 'var(--ink-2)';
  return (
    <button
      onClick={onClick}
      onContextMenu={onContextMenu}
      onMouseEnter={(e) => { setHover(true); if (!isSelected) e.currentTarget.style.background = 'var(--hover)'; }}
      onMouseLeave={(e) => { setHover(false); if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
      className="row row-gap"
      style={{
        width: '100%',
        height: 30,
        padding: '0 10px',
        borderRadius: 8,
        background: tinted
          ? `color-mix(in srgb, ${p.color} 18%, var(--bg-side))`
          : isSelected ? 'var(--selected)' : 'transparent',
        color: tinted ? `color-mix(in srgb, ${p.color} 90%, var(--ink))` : 'var(--ink)',
        position: 'relative',
        textAlign: 'left',
        opacity: p.muted || needsProvider ? 0.55 : 1,
      }}
    >
      {needsProvider
        ? <span style={{ width: 9, height: 9, transform: 'rotate(45deg)', borderRadius: 1.5, border: '1.5px solid ' + p.color, display: 'inline-block', flexShrink: 0 }} />
        : <span className="diamond" style={{ '--c': p.color }} />
      }
      <span style={{ flex: 1, fontSize: 13, fontWeight: nameWeight, color: nameColor }}>{p.id}</span>
      {p.muted && <window.I.MuteIcon style={{ width: 11, height: 11, color: 'var(--ink-4)' }} />}
      {hover && !hideTs ? (
        <span
          onClick={(e) => { e.stopPropagation(); onPinToggle?.(); }}
          style={{ display: 'inline-flex', padding: 2, borderRadius: 4, color: p.pinned ? 'var(--ink-2)' : 'var(--ink-4)' }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--line)'; e.currentTarget.style.color = 'var(--ink)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = p.pinned ? 'var(--ink-2)' : 'var(--ink-4)'; }}
        >
          <window.PinIcon filled={p.pinned} />
        </span>
      ) : (
        <>
          {!hideTs && p.unread && <span className="dot pulse-dot" style={{ '--c': p.color, width: 6, height: 6 }} />}
          {!hideTs && !p.unread && p.lastTs && <span style={{ fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--font-mono)' }}>{p.lastTs}</span>}
        </>
      )}
    </button>
  );
}

// derive a workgroup's current state by scanning its thread for the latest marker
function deriveWgState(wg) {
  if (wg.status === 'paused') return 'idle';
  const threadName = ({
    customers: 'CUSTOMERS_THREAD',
    architecture: 'ARCHITECTURE_THREAD',
  })[wg.id];
  const thread = threadName ? window.MOCK[threadName] : null;
  if (!thread) return 'idle';
  let lastTask = null;
  for (const m of thread) {
    if (m.marker === 'task') lastTask = { id: m.taskId, closed: false };
    if (lastTask && m.taskId === lastTask.id && (m.marker === 'done' || m.marker === 'skip')) {
      lastTask.closed = true;
    }
  }
  if (!lastTask) return 'idle';
  return lastTask.closed ? 'done' : 'working';
}
window.deriveWgState = deriveWgState;

function WorkgroupRow({ wg, active, onClick, density, showColorWash, onContextMenu, onPinToggle }) {
  const isSelected = active;
  const tinted = showColorWash && isSelected;
  const state = deriveWgState(wg);
  const isPaused = wg.status === 'paused';
  const [hover, setHover] = useState(false);

  const icon =
    state === 'working' ? (
      <span style={{ display: 'inline-flex', color: wg.color }}>
        <window.Activity size="sm" />
      </span>
    ) : state === 'done' ? (
      <window.I.Check style={{ width: 13, height: 13, strokeWidth: 2, color: wg.color }} />
    ) : isPaused ? (
      <window.I.Pause style={{ width: 11, height: 11, strokeWidth: 2, color: 'var(--ink-4)' }} />
    ) : (
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        border: '1.5px solid var(--ink-4)',
        display: 'inline-block',
      }} />
    );

  return (
    <button
      onClick={onClick}
      onContextMenu={onContextMenu}
      onMouseEnter={(e) => { setHover(true); if (!isSelected) e.currentTarget.style.background = 'var(--hover)'; }}
      onMouseLeave={(e) => { setHover(false); if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
      className="row row-gap"
      style={{
        width: '100%',
        height: 30,
        padding: '0 10px',
        borderRadius: 8,
        background: tinted
          ? `color-mix(in srgb, ${wg.color} 14%, var(--bg-side))`
          : isSelected ? 'var(--selected)' : 'transparent',
        textAlign: 'left',
        opacity: wg.muted ? 0.55 : 1,
      }}
    >
      <span style={{ width: 14, display: 'inline-flex', justifyContent: 'center' }}>{icon}</span>
      <span style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: isSelected ? 500 : 400, color: tinted || isSelected ? 'var(--ink)' : 'var(--ink-3)' }}>
        #{wg.id}
      </span>
      {wg.muted && <window.I.MuteIcon style={{ width: 11, height: 11, color: 'var(--ink-4)' }} />}
      {hover ? (
        <span
          onClick={(e) => { e.stopPropagation(); onPinToggle?.(); }}
          style={{ display: 'inline-flex', padding: 2, borderRadius: 4, color: wg.pinned ? 'var(--ink-2)' : 'var(--ink-4)' }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--line)'; e.currentTarget.style.color = 'var(--ink)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = wg.pinned ? 'var(--ink-2)' : 'var(--ink-4)'; }}
        >
          <window.PinIcon filled={wg.pinned} />
        </span>
      ) : (
        wg.lastTs && <span style={{ fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--font-mono)' }}>{wg.lastTs}</span>
      )}
    </button>
  );
}

function SectionLabel({ children, right }) {
  return (
    <div className="row between" style={{ padding: '14px 10px 6px', minHeight: 22 }}>
      <span className="eyebrow" style={{ paddingLeft: 2 }}>{children}</span>
      {right}
    </div>
  );
}

// ── ThemeButton — cycles light → dark → system ──────────────────────────
// Persists choice in localStorage. 'system' follows prefers-color-scheme live.
function ThemeButton() {
  const get = () => {
    try { return localStorage.getItem('alpi-theme') || 'system'; } catch { return 'system'; }
  };
  const [mode, setMode] = React.useState(get);

  React.useEffect(() => {
    const apply = (m) => {
      const effective = m === 'system'
        ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
        : m;
      document.documentElement.setAttribute('data-mode', effective);
    };
    apply(mode);
    try { localStorage.setItem('alpi-theme', mode); } catch {}

    if (mode === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      const onChange = () => apply('system');
      mq.addEventListener?.('change', onChange);
      return () => mq.removeEventListener?.('change', onChange);
    }
  }, [mode]);

  const cycle = () => setMode(m => m === 'light' ? 'dark' : m === 'dark' ? 'system' : 'light');
  const next = mode === 'light' ? 'dark' : mode === 'dark' ? 'system' : 'light';
  const Icon = mode === 'light' ? window.I.Sun : mode === 'dark' ? window.I.Moon : window.I.Auto;

  return (
    <window.Tip text={`Theme: ${mode} · click for ${next}`} side="up">
      <button className="iconbtn" onClick={cycle} aria-label={`Theme: ${mode}`}>
        <Icon style={{ width: 14, height: 14 }} />
      </button>
    </window.Tip>
  );
}
window.ThemeButton = ThemeButton;

// ── VersionButton — click to check for updates ──────────────────────────
// States: 'idle' → click → 'checking' → after 1.2s → 'up-to-date' OR 'update-available'.
// Demo: alternates each click between up-to-date and update-available.
function VersionButton({ current = '0.3.0' }) {
  const [state, setState] = React.useState('idle');
  const [open, setOpen] = React.useState(false);
  const [showUpdate, setShowUpdate] = React.useState(false);
  const [lastChecked, setLastChecked] = React.useState(null);
  const ref = React.useRef(null);

  React.useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const onClick = () => {
    setOpen(true);
    setState('checking');
    setTimeout(() => {
      const willOffer = showUpdate;
      setShowUpdate(v => !v);
      setLastChecked(new Date());
      setState(willOffer ? 'update-available' : 'up-to-date');
    }, 1100);
  };

  return (
    <span ref={ref} style={{ position: 'relative' }}>
      <window.Tip text="Check for updates" side="up">
        <button
          onClick={onClick}
          className="mono"
          style={{
            color: 'var(--ink-4)', fontSize: 11,
            padding: '2px 4px', margin: '-2px -4px',
            borderRadius: 4,
            transition: 'color .12s, background .12s',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--ink-2)'; e.currentTarget.style.background = 'var(--hover)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--ink-4)'; e.currentTarget.style.background = 'transparent'; }}
        >{current}</button>
      </window.Tip>
      {open && (
        <div className="anim-pop" style={{
          position: 'absolute', bottom: 'calc(100% + 8px)', right: 0,
          width: 220, background: 'var(--bg-elev)',
          border: '.5px solid var(--line-2)', borderRadius: 12,
          boxShadow: 'var(--shadow)', zIndex: 50,
        }}>
          <VersionContent state={state} current={current} lastChecked={lastChecked} onClose={() => setOpen(false)} />
        </div>
      )}
    </span>
  );
}

function VersionContent({ state, current, lastChecked, onClose }) {
  if (state === 'checking') {
    return (
      <div className="col" style={{ padding: 16, gap: 10 }}>
        <div className="row row-gap" style={{ gap: 10 }}>
          <span style={{ display: 'inline-flex', color: 'var(--ink-3)' }}>
            <window.Activity size="md" />
          </span>
          <span style={{ fontSize: 13, color: 'var(--ink-2)' }}>Checking for updates…</span>
        </div>
        <span className="mono" style={{ fontSize: 11, color: 'var(--ink-4)' }}>Talking to releases.alpi.dev</span>
      </div>
    );
  }
  if (state === 'up-to-date') {
    return (
      <div className="col" style={{ padding: 16, gap: 10 }}>
        <div className="row row-gap" style={{ gap: 8 }}>
          <window.I.Check style={{ width: 14, height: 14, strokeWidth: 2.2, color: 'var(--c-success)' }} />
          <span style={{ fontSize: 13, fontWeight: 500 }}>You're up to date</span>
        </div>
        <div className="col" style={{ gap: 2, fontSize: 11, color: 'var(--ink-3)' }}>
          <span><span style={{ color: 'var(--ink-4)' }}>Current</span> <span className="mono" style={{ color: 'var(--ink-2)' }}>{current}</span></span>
          <span><span style={{ color: 'var(--ink-4)' }}>Last checked</span> <span className="mono" style={{ color: 'var(--ink-2)' }}>just now</span></span>
        </div>
      </div>
    );
  }
  if (state === 'update-available') {
    return (
      <div className="col" style={{ padding: 16, gap: 12 }}>
        <div className="col" style={{ gap: 4 }}>
          <div className="row row-gap" style={{ gap: 8 }}>
            <span className="dot pulse-dot" style={{ '--c': 'var(--c-success)', width: 8, height: 8 }} />
            <span style={{ fontSize: 13, fontWeight: 500 }}>Update available</span>
          </div>
          <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>
            {current} → <span style={{ color: 'var(--c-success)', fontWeight: 600 }}>0.4.0</span>
          </span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 'var(--lh-normal)', padding: '8px 10px', background: 'var(--hover)', borderRadius: 6 }}>
          New in 0.4.0: <strong>Voice mode</strong>, faster <code className="mono" style={{ fontSize: 11, background: 'var(--bg-elev)', padding: '0 4px', borderRadius: 3 }}>link.ask</code>, fix for schedule drift.
        </div>
        <div className="row between">
          <button
            className="alink"
            onClick={(e) => { e.stopPropagation(); }}
            onMouseEnter={e => { e.currentTarget.style.textDecoration = 'underline'; }}
            onMouseLeave={e => { e.currentTarget.style.textDecoration = 'none'; }}
          >Changelog</button>
          <button className="btn btn-primary" style={{ height: 26, fontSize: 12 }}>
            Restart &amp; install
          </button>
        </div>
      </div>
    );
  }
  return null;
}

window.VersionButton = VersionButton;

function Sidebar({ state, ui, ms }) {
  const { activeId, activeKind, remote, view, density, dir, wayfinding, settingsTarget, firstRun, daemonOffline } = state;
  const showColorWash = wayfinding === 'strong';
  const PROFILES_BASE = firstRun
    ? window.MOCK.PROFILES.filter(p => p.id === 'alpi').map(p => ({ ...p, pinned: true }))
    : window.MOCK.PROFILES;
  const WORKGROUPS_BASE = firstRun ? [] : window.MOCK.WORKGROUPS;

  // Local UI state — pinned/muted overrides on top of mock data
  const [overrides, setOverrides] = useState(() => {
    // Seed muted = false for everything; pinned comes from mock
    return { profiles: {}, workgroups: {} };
  });

  const PROFILES = PROFILES_BASE.map(p => {
    const o = overrides.profiles[p.id] || {};
    return { ...p, pinned: o.pinned ?? p.pinned, muted: o.muted ?? false };
  });
  const WORKGROUPS = WORKGROUPS_BASE.map(w => {
    const o = overrides.workgroups[w.id] || {};
    return { ...w, pinned: o.pinned ?? false, muted: o.muted ?? false };
  });

  const setProfile = (id, patch) => {
    setOverrides(o => ({ ...o, profiles: { ...o.profiles, [id]: { ...o.profiles[id], ...patch } } }));
  };
  const setWorkgroup = (id, patch) => {
    setOverrides(o => ({ ...o, workgroups: { ...o.workgroups, [id]: { ...o.workgroups[id], ...patch } } }));
  };

  const pinned = PROFILES.filter(p => p.pinned);
  const pinnedWg = WORKGROUPS.filter(w => w.pinned);
  const rest = PROFILES.filter(p => !p.pinned);
  const restWg = WORKGROUPS.filter(w => !w.pinned);
  const [showAll, setShowAll] = useState(false);
  const restShown = showAll ? rest : rest.slice(0, 6);

  const isSettings = view === 'settings';

  const decorate = (p, i) => ({
    ...p,
    lastTs: i % 4 === 1 ? 'now' : '7h',
    unread: p.id === 'doc',
  });

  const onPick = (kind, id) => {
    if (isSettings) ui.setSettingsTarget({ kind, id });
    else ui.openChat({ kind, id });
  };
  const isActive = (kind, id) => {
    if (isSettings) return settingsTarget.kind === kind && settingsTarget.id === id;
    return view === 'chat' && activeKind === kind && activeId === id;
  };

  const openProfileCtx = (e, p) => {
    window.openContextMenu(e, [
      { label: p.pinned ? 'Unpin from top' : 'Pin to top', icon: <window.PinIcon filled={!p.pinned} />, onClick: () => setProfile(p.id, { pinned: !p.pinned }) },
      { label: p.muted ? 'Unmute' : 'Mute notifications', icon: <window.I.Bell />, onClick: () => setProfile(p.id, { muted: !p.muted }) },
      { label: 'Mark as read', icon: <window.I.Check />, shortcut: '⇧⌘R', onClick: () => {} },
      { kind: 'separator' },
      { label: 'Open settings', icon: <window.I.Gear />, shortcut: '⌘,', onClick: () => ui.setSettingsTarget({ kind: 'profile', id: p.id }) },
      { kind: 'separator' },
      { label: 'Delete profile…', icon: <window.I.Trash />, kind: 'danger', onClick: () => ui.setSettingsTarget({ kind: 'profile', id: p.id }) },
    ]);
  };
  const openWgCtx = (e, w) => {
    window.openContextMenu(e, [
      { label: w.pinned ? 'Unpin from top' : 'Pin to top', icon: <window.PinIcon filled={!w.pinned} />, onClick: () => setWorkgroup(w.id, { pinned: !w.pinned }) },
      { label: w.muted ? 'Unmute' : 'Mute notifications', icon: <window.I.Bell />, onClick: () => setWorkgroup(w.id, { muted: !w.muted }) },
      { label: 'Mark as read', icon: <window.I.Check />, onClick: () => {} },
      { kind: 'separator' },
      { label: 'Archive workgroup', icon: <window.I.Archive />, onClick: () => window.notify?.(`#${w.id} archived`, { kind: 'info' }) },
      { label: 'Open settings', icon: <window.I.Gear />, shortcut: '⌘,', onClick: () => ui.setSettingsTarget({ kind: 'workgroup', id: w.id }) },
      { kind: 'separator' },
      { label: 'Delete workgroup…', icon: <window.I.Trash />, kind: 'danger', onClick: () => ui.setSettingsTarget({ kind: 'workgroup', id: w.id }) },
    ]);
  };

  return (
    <aside className="col" style={{
      background: 'var(--bg-side)',
      borderRight: '.5px solid var(--line)',
      minWidth: 0,
      minHeight: 0,
      maxHeight: '100%',
      height: '100%',
      paddingTop: 38, // titlebar
    }}>
      {isSettings && (
        <div className="row row-gap" style={{ gap: 6, padding: '4px 16px 10px' }}>
          <window.Tip text="Back to chat" side="l">
            <button className="iconbtn" onClick={() => ui.setView('chat')}>
              <window.I.ArrowLeft />
            </button>
          </window.Tip>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Settings</span>
          <span style={{ flex: 1 }} />
          <span className="kbd">⌘,</span>
        </div>
      )}
      <div style={{ padding: '6px 12px 4px' }}>
        <SectionLabel>Connection</SectionLabel>
        <ConnectionCell remote={remote} onOpenPicker={() => ui.openPanel('connection')} offline={daemonOffline} />
      </div>

      {!isSettings && (
        <div style={{ padding: '8px 12px 0' }}>
          <button
            onClick={() => ui.openChat({ kind: 'new', id: null })}
            className="row row-gap"
            style={{
              width: '100%', height: 32, padding: '0 10px', borderRadius: 8,
              background: view === 'new' ? 'var(--selected)' : 'transparent',
              color: 'var(--ink-2)',
              textAlign:'left',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={e => { if (view !== 'new') e.currentTarget.style.background = 'var(--hover)'; }}
            onMouseLeave={e => { if (view !== 'new') e.currentTarget.style.background = 'transparent'; }}
          >
            <window.I.Plus />
            <span style={{ fontSize: 13, flex: 1 }}>New chat</span>
            <span style={{ display:'flex', gap:2, flexShrink: 0 }}>
              <span className="kbd">⌘</span><span className="kbd">N</span>
            </span>
          </button>
        </div>
      )}

      <div className="scroll" style={{ flex: 1, padding: '0 12px 12px' }}>
        {(pinned.length + pinnedWg.length > 0) && (
          <>
            <SectionLabel>Pinned</SectionLabel>
            <div className="col" style={{ gap: 1 }}>
              {pinned.map((p, i) => (
                <ProfileRow
                  key={p.id}
                  p={decorate(p, i)}
                  active={isActive('profile', p.id)}
                  onClick={() => onPick('profile', p.id)}
                  density={density} dir={dir}
                  showColorWash={showColorWash}
                  hideTs={isSettings}
                  onContextMenu={(e) => openProfileCtx(e, p)}
                  onPinToggle={() => setProfile(p.id, { pinned: !p.pinned })}
                />
              ))}
              {pinnedWg.map((wg, i) => (
                <WorkgroupRow
                  key={wg.id}
                  wg={{ ...wg, lastTs: !isSettings && i === 0 ? 'now' : null }}
                  active={isActive('workgroup', wg.id)}
                  onClick={() => onPick('workgroup', wg.id)}
                  density={density} showColorWash={showColorWash}
                  onContextMenu={(e) => openWgCtx(e, wg)}
                  onPinToggle={() => setWorkgroup(wg.id, { pinned: !wg.pinned })}
                />
              ))}
            </div>
          </>
        )}

        <SectionLabel right={
          <window.Tip text="New profile" side="r">
            <button className="iconbtn" style={{ width: 18, height: 18 }} onClick={() => ui.openPanel('new-profile')}>
              <window.I.Plus style={{ width: 12, height: 12, strokeWidth: 2 }} />
            </button>
          </window.Tip>
        }>{isSettings ? 'Profiles' : 'Alpis'}</SectionLabel>
        <div className="col" style={{ gap: 1 }}>
          {restShown.map((p, i) => (
            <ProfileRow
              key={p.id}
              p={decorate(p, i + 4)}
              active={isActive('profile', p.id)}
              onClick={() => onPick('profile', p.id)}
              density={density} dir={dir}
              showColorWash={showColorWash}
              hideTs={isSettings}
              onContextMenu={(e) => openProfileCtx(e, p)}
              onPinToggle={() => setProfile(p.id, { pinned: !p.pinned })}
            />
          ))}
          {rest.length > restShown.length && (
            <button
              onClick={() => setShowAll(s => !s)}
              style={{ padding: '6px 10px', borderRadius: 8, textAlign: 'left', fontSize: 12, color: 'var(--ink-3)' }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
            >{showAll ? 'Collapse' : `Show ${rest.length - restShown.length} more`}</button>
          )}
        </div>

        <SectionLabel right={
          <window.Tip text="New workgroup" side="r">
            <button className="iconbtn" style={{ width: 18, height: 18 }} onClick={() => ui.openPanel('new-workgroup')}>
              <window.I.Plus style={{ width: 12, height: 12, strokeWidth: 2 }} />
            </button>
          </window.Tip>
        }>Workgroups</SectionLabel>
        <div className="col" style={{ gap: 1 }}>
          {restWg.map((wg, i) => (
            <WorkgroupRow
              key={wg.id}
              wg={{ ...wg, lastTs: !isSettings && i === 1 ? 'now' : (isSettings ? null : '7h') }}
              active={isActive('workgroup', wg.id)}
              onClick={() => onPick('workgroup', wg.id)}
              density={density} showColorWash={showColorWash}
              onContextMenu={(e) => openWgCtx(e, wg)}
              onPinToggle={() => setWorkgroup(wg.id, { pinned: !wg.pinned })}
            />
          ))}
        </div>
      </div>

      <div style={{
        padding: '10px 12px',
        borderTop: '.5px solid var(--line)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        {!isSettings ? (
          <button
            className="row row-gap"
            onClick={() => ui.setView('settings')}
            style={{ flex: 1, height: 28, padding: '0 8px', borderRadius: 8, color: 'var(--ink-2)', textAlign: 'left' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            <window.I.Gear />
            <span style={{ fontSize: 13 }}>Settings</span>
            <span style={{ marginLeft: 'auto', display:'flex', gap:2 }}>
              <span className="kbd">⌘</span><span className="kbd">,</span>
            </span>
          </button>
        ) : (
          <button
            className="row row-gap"
            onClick={() => ui.openPalette()}
            style={{ flex: 1, height: 28, padding: '0 8px', borderRadius: 8, color: 'var(--ink-2)', textAlign: 'left' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            <window.I.Search />
            <span style={{ fontSize: 13 }}>Command…</span>
            <span style={{ marginLeft: 'auto', display:'flex', gap:2 }}>
              <span className="kbd">⌘</span><span className="kbd">K</span>
            </span>
          </button>
        )}
        <ThemeButton />
        <VersionButton current="0.3.0" />
      </div>
    </aside>
  );
}

window.Sidebar = Sidebar;
