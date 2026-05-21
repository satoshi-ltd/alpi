// app.jsx — wires sidebar + main content + tweaks + overlays.

const { useState: useStateA, useEffect: useEffectA, useMemo: useMemoA, useRef: useRefA } = React;

function App() {
  const [t, setTweak] = useTweaks(window.TWEAK_DEFAULTS);

  // App state
  const [view, setView] = useStateA('chat');                  // 'chat' | 'settings' | 'new'
  const [activeKind, setActiveKind] = useStateA('workgroup');
  const [activeId, setActiveId] = useStateA('customers');
  const [settingsTarget, setSettingsTarget] = useStateA({ kind: 'profile', id: 'builder' });
  const [remote, setRemote] = useStateA(window.MOCK.REMOTES[0]);
  const [panel, setPanel] = useStateA(null);     // 'connection' | 'skills' | 'memory' | 'tools' | 'new-profile' | 'new-workgroup' | 'providers' | null
  const [paletteOpen, setPaletteOpen] = useStateA(false);
  const [threads, setThreadsState] = useStateA({});

  const setThread = (key, val) => {
    setThreadsState(prev => ({ ...prev, [key]: val }));
  };

  // UI bridge
  const ui = useMemoA(() => ({
    setView,
    openChat: ({ kind, id }) => {
      if (kind === 'new') { setView('new'); return; }
      setActiveKind(kind);
      setActiveId(id);
      setView('chat');
    },
    setSettingsTarget: (t) => {
      setSettingsTarget(t);
      setView('settings');
    },
    openSettingsFor: (subject) => {
      setSettingsTarget({ kind: subject.kind, id: subject.id });
      setView('settings');
    },
    openPanel: (which) => setPanel(which),
    closePanel: () => setPanel(null),
    openPalette: () => setPaletteOpen(true),
    closePalette: () => setPaletteOpen(false),
    setRemote: (r) => setRemote(r),
  }), []);

  const state = {
    activeKind, activeId, remote, view, threads, setThread,
    settingsTarget,
    style: t.style,
    dir: 'console',
    density: 'compact',
    wayfinding: t.wayfinding,
    daemonOffline: t.daemonOffline,
    firstRun: t.firstRun,
  };

  // Theme attributes on root — direction is locked to console
  useEffectA(() => {
    document.documentElement.setAttribute('data-direction', 'console');
    document.documentElement.setAttribute('data-style', t.style);
    document.documentElement.setAttribute('data-mode', t.dark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-density', 'compact');
    document.documentElement.setAttribute('data-show-tips', String(!!t.showTips));
  }, [t.style, t.dark, t.showTips]);

  // Keyboard shortcuts
  useEffectA(() => {
    const onKey = (e) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(p => !p);
      } else if (mod && e.key.toLowerCase() === 'n' && !e.shiftKey) {
        e.preventDefault(); setView('new');
      } else if (mod && e.key === ',') {
        e.preventDefault(); setView('settings');
      } else if (e.key === 'Escape') {
        if (paletteOpen) setPaletteOpen(false);
        else if (panel) setPanel(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [panel, paletteOpen]);

  // Light demo: fire 1 notification a moment after mount.
  useEffectA(() => {
    const t = setTimeout(() => {
      window.notify?.('workgroups disabled · daemon restarting', { kind: 'success' });
    }, 900);
    return () => clearTimeout(t);
  }, []);

  let content;
  if (view === 'settings') content = <SettingsView state={state} ui={ui} />;
  else if (view === 'new') content = <NewChatView state={state} ui={ui} />;
  else content = <ChatView state={state} ui={ui} />;

  const accent = useMemoA(() => {
    const find = activeKind === 'profile'
      ? window.MOCK.PROFILES.find(p => p.id === activeId)
      : window.MOCK.WORKGROUPS.find(w => w.id === activeId);
    return find?.color || 'var(--ink-2)';
  }, [activeKind, activeId]);

  return (
    <div className="surround" style={{ '--accent': accent }}>
      <div className="window">
        <div className="titlebar">
          <div className="tl"><span /><span /><span /></div>
        </div>

        <Sidebar state={state} ui={ui} />
        <main style={{ minWidth: 0, position: 'relative', background: 'var(--bg-pane)' }}>
          {content}
        </main>

        {panel === 'connection' && <ConnectionPanel state={state} ui={ui} />}
        {panel === 'skills' && <SkillsPanel state={state} ui={ui} />}
        {panel === 'memory' && <MemoryPanel state={state} ui={ui} />}
        {panel === 'tools' && <ToolsPanel state={state} ui={ui} />}
        <NewProfileModal
          open={panel === 'new-profile'}
          onClose={() => setPanel(null)}
          onOpenProviders={() => setPanel('providers')}
          onCreate={(p) => {
            window.notify?.(`Profile @${p.id} created`, { kind: 'success' });
            setSettingsTarget({ kind: 'profile', id: p.id });
            setView('settings');
          }}
        />
        <window.ProvidersModal
          open={panel === 'providers'}
          onClose={() => setPanel('new-profile')}
        />
        <NewWorkgroupModal
          open={panel === 'new-workgroup'}
          onClose={() => setPanel(null)}
          onCreate={(w) => {
            window.notify?.(`Workgroup #${w.id} created`, { kind: 'success' });
            setSettingsTarget({ kind: 'workgroup', id: w.id });
            setView('settings');
          }}
        />
        {paletteOpen && <Palette state={state} ui={ui} />}
      </div>

      <NotificationStack />
      <ContextMenuMount />

      <TweaksPanel>
        <TweakSection label="Style" />
        <TweakSelect
          label="Variant"
          value={t.style}
          options={['studio', 'brutalist', 'muji']}
          onChange={(v) => setTweak('style', v)}
        />
        <TweakRadio
          label="Wayfinding"
          value={t.wayfinding}
          options={['subtle', 'strong']}
          onChange={(v) => setTweak('wayfinding', v)}
        />
        <TweakToggle
          label="Dark mode"
          value={t.dark}
          onChange={(v) => setTweak('dark', v)}
        />
        <TweakToggle
          label="Show tooltips"
          value={t.showTips}
          onChange={(v) => setTweak('showTips', v)}
        />

        <TweakSection label="App state" />
        <TweakToggle label="Daemon offline" value={t.daemonOffline} onChange={(v) => setTweak('daemonOffline', v)} />
        <TweakToggle label="First-run (no profiles yet)" value={t.firstRun} onChange={(v) => setTweak('firstRun', v)} />

        <TweakSection label="Notifications" />
        <div className="col" style={{ gap: 4 }}>
          <TweakButton label="System · daemon restarting" onClick={() => window.notify('workgroups disabled · daemon restarting', { kind: 'success' })} />
          <TweakButton label="Info · context updated" onClick={() => window.notify('@pantry · shopping list updated', { kind: 'info' })} />
          <TweakButton label="Warning · budget 80%" onClick={() => window.notify('#roadmap · budget at 80%', { kind: 'warning' })} />
          <TweakButton label="Danger · peer offline" onClick={() => window.notify('umbrel.etxea · peer offline', { kind: 'danger' })} />
          <TweakButton label="With action" onClick={() => window.notify({ text: 'New schedule failed', kind: 'danger', action: 'Retry', onAction: () => window.notify('Retrying…', { kind: 'success' }) })} />
        </div>

        <TweakSection label="Open" />
        <div className="col" style={{ gap: 4 }}>
          <TweakButton label="Command palette  ⌘K" onClick={() => setPaletteOpen(true)} />
          <TweakButton label="Skills" onClick={() => setPanel('skills')} />
          <TweakButton label="Memory" onClick={() => setPanel('memory')} />
          <TweakButton label="Tools" onClick={() => setPanel('tools')} />
          <TweakButton label="Connection picker" onClick={() => setPanel('connection')} />
        </div>

        <TweakSection label="Go to" />
        <div className="col" style={{ gap: 4 }}>
          <TweakButton label="Chat — #customers" onClick={() => { setActiveKind('workgroup'); setActiveId('customers'); setView('chat'); }} />
          <TweakButton label="Chat — @doc" onClick={() => { setActiveKind('profile'); setActiveId('doc'); setView('chat'); }} />
          <TweakButton label="New chat" onClick={() => setView('new')} />
          <TweakButton label="Settings — @builder" onClick={() => { setSettingsTarget({ kind: 'profile', id: 'builder' }); setView('settings'); }} />
          <TweakButton label="Settings — #roadmap" onClick={() => { setSettingsTarget({ kind: 'workgroup', id: 'roadmap' }); setView('settings'); }} />
        </div>
      </TweaksPanel>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
