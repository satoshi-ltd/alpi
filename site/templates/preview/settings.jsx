// settings.jsx — flat-form settings (matches the existing app's structure)
// Section headers + key/value rows, no card containers.

const { useState: useStateS, useMemo: useMemoS } = React;

// ── primitives ────────────────────────────────────────────────────────────
function Section({ label, children, kicker }) {
  return (
    <section style={{ marginTop: 36 }}>
      <div className="row" style={{ alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
        <h3 style={{
          margin: 0,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '.10em',
          textTransform: 'uppercase',
          color: 'var(--ink-2)',
          fontFamily: 'var(--font-mono)',
        }}>{label}</h3>
        {kicker && <span style={{ fontSize: 11, color: 'var(--ink-4)' }}>{kicker}</span>}
      </div>
      <div className="col" style={{ gap: 0 }}>{children}</div>
    </section>
  );
}

function Field({ label, children, helper, align = 'center' }) {
  return (
    <div className="row" style={{ alignItems: align === 'center' ? 'center' : 'flex-start', gap: 24, padding: '8px 0' }}>
      <div style={{ width: 96, flexShrink: 0, paddingTop: align === 'top' ? 6 : 0 }}>
        <div className="eyebrow" style={{ fontSize: 11 }}>{label}</div>
        {helper && <div style={{ fontSize: 11, color: 'var(--ink-4)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>{helper}</div>}
      </div>
      <div className="row" style={{ flex: 1, minWidth: 0, alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        {children}
      </div>
    </div>
  );
}

// inline pill-shaped select trigger
function Selectish({ children, onClick }) {
  return (
    <button onClick={onClick} className="row row-gap" style={{
      gap: 8, padding: '6px 12px', borderRadius: 8,
      background: 'var(--bg-input)', border: '.5px solid var(--line-2)',
      fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink)',
    }}>
      {children}
      <window.I.ChevDown style={{ width: 12, height: 12, color: 'var(--ink-3)' }} />
    </button>
  );
}

// Trigger + anchored popover wrapper — reused everywhere in settings
function Popped({ trigger, width = 320, children, mode = 'selectish', align = 'left' }) {
  const [open, setOpen] = useStateS(false);
  const TriggerEl = mode === 'selectish' ? Selectish : ActionLink;
  return (
    <span style={{ position: 'relative' }}>
      <TriggerEl onClick={() => setOpen(o => !o)}>{trigger}</TriggerEl>
      <window.Anchored open={open} onClose={() => setOpen(false)} width={width} align={align}>
        {typeof children === 'function' ? children({ close: () => setOpen(false) }) : children}
      </window.Anchored>
    </span>
  );
}

function ActionLink({ children, onClick, danger }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 8px', margin: '-4px -8px',
        borderRadius: 6,
        fontSize: 13,
        color: danger ? '#c14545' : 'var(--ink-2)',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'var(--hover)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >{children}</button>
  );
}

// ── Accent picker ────────────────────────────────────────────────────────
const ACCENT_SWATCHES = [
  '#b8954a', // alpi gold (default)
  '#d97757', // terracotta
  '#c14545', // brick red
  '#c14580', // magenta
  '#9d4dc6', // purple
  '#6a6dd6', // indigo
  '#3d7ea6', // denim
  '#2f8e9e', // teal
  '#2f7d6e', // pine
  '#3fb37a', // forest
  '#8a7a4a', // olive
  '#6c7480', // slate
];

function AccentPicker({ value, onChange }) {
  const [open, setOpen] = useStateS(false);
  const [hex, setHex] = useStateS(value || '#b8954a');
  const ref = React.useRef(null);

  React.useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const commit = (c) => {
    setHex(c);
    onChange?.(c);
  };

  const isValidHex = /^#[0-9a-f]{6}$/i.test(hex);

  return (
    <span ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="row row-gap"
        style={{
          gap: 8, padding: '6px 12px', borderRadius: 8,
          background: 'var(--bg-input)', border: '.5px solid var(--line-2)',
          fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink)',
        }}
      >
        <span style={{ width: 11, height: 11, transform: 'rotate(45deg)', borderRadius: 2, background: value, display: 'inline-block', boxShadow: 'inset 0 0 0 .5px rgba(0,0,0,.15)' }} />
        <span>{value}</span>
        <window.I.ChevDown style={{ width: 12, height: 12, color: 'var(--ink-3)' }} />
      </button>
      {open && (
        <div className="anim-pop" style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0,
          width: 256, background: 'var(--bg-elev)',
          border: '.5px solid var(--line-2)', borderRadius: 12,
          boxShadow: 'var(--shadow)', zIndex: 30,
          padding: 14,
        }}>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 16,
            padding: '8px 4px 12px',
            marginBottom: 4,
            justifyItems: 'center', alignItems: 'center',
          }}>
            {ACCENT_SWATCHES.map(c => {
              const sel = value?.toLowerCase() === c.toLowerCase();
              return (
                <button
                  key={c}
                  onClick={() => commit(c)}
                  title={c}
                  style={{
                    width: 24, height: 24, borderRadius: 3,
                    background: c, position: 'relative',
                    transform: sel ? 'rotate(45deg) scale(1.05)' : 'rotate(45deg)',
                    boxShadow: sel
                      ? `inset 0 0 0 1.5px var(--bg-elev), 0 0 0 2px var(--ink)`
                      : `inset 0 0 0 .5px rgba(0,0,0,.18)`,
                    transition: 'transform .12s, box-shadow .12s',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e => { if (!sel) e.currentTarget.style.transform = 'rotate(45deg) scale(1.12)'; }}
                  onMouseLeave={e => { if (!sel) e.currentTarget.style.transform = 'rotate(45deg)'; }}
                />
              );
            })}
          </div>
          <input
            value={hex}
            onChange={e => {
              setHex(e.target.value);
              if (/^#[0-9a-f]{6}$/i.test(e.target.value)) onChange?.(e.target.value);
            }}
            className="field field-mono"
            placeholder="#hex"
            style={{ padding: '8px 10px', height: 32, fontSize: 12 }}
            spellCheck={false}
          />
          {!isValidHex && hex.length > 0 && (
            <div style={{ marginTop: 6, fontSize: 11, color: 'var(--c-danger)', fontFamily: 'var(--font-mono)' }}>
              must be 6-digit #hex
            </div>
          )}
        </div>
      )}
    </span>
  );
}

// ── Profile detail ────────────────────────────────────────────────────────
const SCHEDULE_BY_PROFILE = {
  doc: [
    { id: '45188EAB', cron: 'cron 0 7 * * *', desc: 'Sync wearable health data and append the latest vitals', on: true },
    { id: '91EC37EA', cron: 'cron 0 19 * * *', desc: 'Import training files and refresh workout notes', on: true },
    { id: '7E4D2A91', cron: 'cron 30 7 * * 0', desc: 'Weekly health review with sleep, recovery, training, and nutrition notes', on: true },
  ],
  pantry: [
    { id: 'B87A9210', cron: 'cron 0 18 * * 4', desc: 'Build next week meal plan from pantry.md and calendar.md', on: true },
    { id: 'C12F2D4B', cron: 'cron 30 9 * * 6', desc: 'Generate grocery list and flag food that should be used soon', on: true },
  ],
  builder: [
    { id: '2160CDE6', cron: 'cron 0 9 * * 1-5', desc: 'Daily repo summary across active workspaces', on: true },
    { id: '41C646BC', cron: 'cron */30 9-18 * * 1-5', desc: 'Review open PRs and flag blocked work', on: true },
  ],
  home: [
    { id: '9AC13D7E', cron: 'cron 15 8 * * *', desc: 'Check backups, package deliveries, and maintenance reminders', on: true },
  ],
};

const SKILLS_BY_PROFILE = {
  doc: ['fitness_sync', 'weekly', 'wearable_sync'],
  pantry: ['meal-plan', 'grocery-sync'],
  builder: ['pr-review', 'repo-summary'],
  home: ['backup-check', 'warranty-tracker'],
};

function ProfileDetail({ id, state, ui }) {
  const p = window.MOCK.PROFILES.find(x => x.id === id);
  if (!p) return null;

  const [identity, setIdentity] = useStateS(p.identity || '');
  const [identityDirty, setIdentityDirty] = useStateS(false);
  const [tcpOn, setTcpOn] = useStateS(false);
  const [terminal, setTerminal] = useStateS(false);
  const [network, setNetwork] = useStateS(false);
  const [voiceId, setVoiceId] = useStateS('aria');
  const [pairOpen, setPairOpen] = useStateS(false);
  const [mcpOpen, setMcpOpen] = useStateS(false);
  const [providersOpen, setProvidersOpen] = useStateS(false);
  const [deleteOpen, setDeleteOpen] = useStateS(false);

  const peers = window.MOCK.PEERS_BY_PROFILE?.[id] || [];
  const peerCount = peers.length;
  const onlineCount = peers.filter(pe => pe.status === 'connected').length;

  // Stateful subsystems & email accounts — 3 states: 'on' (working) · 'err' (error) · 'off' (disabled)
  const [subsState, setSubsState] = useStateS({ schedule: 'on', alp: 'on', workgroups: 'err' });
  const [emailState, setEmailState] = useStateS({ imap: 'off', gmail: 'off' });
  const cycle = (v) => v === 'on' ? 'off' : v === 'off' ? 'on' : 'on'; // err → on on click (acknowledge)
  const toggleSub = (k) => setSubsState(s => ({ ...s, [k]: cycle(s[k]) }));
  const toggleEmail = (k) => setEmailState(s => ({ ...s, [k]: cycle(s[k]) }));

  const subs = ['schedule', 'alp', 'workgroups'];
  const emailAccounts = ['imap', 'gmail'];

  const schedule = SCHEDULE_BY_PROFILE[id] || [
    { id: '2160CDE6', cron: 'cron 30 6 * * *', desc: "Use the `good-morning` skill to generate today's scheduled morning greeting…", on: true },
  ];

  const skills = SKILLS_BY_PROFILE[id] || [];
  const voice = window.VOICES.find(v => v.id === voiceId) || window.VOICES[0];

  return (
    <div className="scroll" style={{ height: '100%', minWidth: 0 }}>
      {/* Hero */}
      <div style={{
        padding: 'var(--hero-pad-top) var(--pane-pad-x) var(--hero-pad-bottom)',
        borderBottom: '.5px solid var(--line)',
        position: 'sticky',
        top: 0,
        zIndex: 5,
        background: 'var(--bg-pane)',
      }}>
        <div className="row between" style={{ alignItems: 'flex-end' }}>
          <div className="col" style={{ gap: 8, flex: 1, minWidth: 0 }}>
            <div className="row row-gap" style={{ gap: 12 }}>
              <span className="diamond" style={{ '--c': p.color, width: 14, height: 14 }} />
              <h1 className="display" style={{
                margin: 0, fontSize: 28, fontWeight: 'var(--display-weight)',
                fontStyle: 'var(--display-italic)', color: 'var(--ink)',
                }}>{p.id}</h1>
              <span className="mono" style={{ color: 'var(--ink-4)', fontSize: 11, marginLeft: 2, alignSelf: 'flex-end', paddingBottom: 4 }}>
                profile · settings
              </span>
            </div>
            <div className="row row-gap" style={{ gap: 14, color: 'var(--ink-3)', fontSize: 12 }}>
              <span className="mono" style={{ color: 'var(--ink-2)' }}>{p.model}</span>
              <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
              <span><span style={{ color: 'var(--ink-4)' }}>budget</span> <span className="mono tnum" style={{ color: 'var(--ink-2)' }}>${(p.used ?? 0).toFixed(2)}/${(p.budget ?? 2).toFixed(2)}</span></span>
            </div>
          </div>
          <window.Tip text="Back to chat · ⌘," side="r">
            <button className="iconbtn" onClick={() => ui.openChat({ kind: 'profile', id: p.id })}>
              <window.I.ArrowLeft />
            </button>
          </window.Tip>
        </div>
        <span style={{
          position: 'absolute', left: 32, bottom: -0.5, height: 1.5,
          width: 40, background: p.color,
        }} />
      </div>

      {/* Body */}
      <div style={{ padding: 'var(--space-9) var(--pane-pad-x) 80px', maxWidth: 920, width: '100%', margin: '0 auto' }}>
        {/* Overview ───────────────────────────────────────────────────── */}
        <Section label="Overview">
          <Field label="Home">
            <span className="mono" style={{ fontSize: 12, color: 'var(--ink-2)' }}>/Users/javi/.alpi/profiles/{p.id}</span>
            <ActionLink>Reveal</ActionLink>
          </Field>
          <Field label="Model">
            <window.ModelPicker currentModel={p.model} accent={p.color} />
            <ActionLink onClick={() => setProvidersOpen(true)}>Providers</ActionLink>
          </Field>
          <Field label="Budget" helper="per day spend cap">
            <Popped trigger={<><window.I.Dollar style={{ width:12, height:12 }} /><span className="tnum">{(p.budget ?? 2).toFixed(2)}/day</span></>} width={260}>
              {({ close }) => <window.BudgetEditPopover value={p.budget ?? 2} onSave={close} />}
            </Popped>
          </Field>
          <Field label="Workspace">
            <input
              className="field field-mono"
              defaultValue={p.workspace || `~/workspaces/${id}`}
              style={{ flex: 1, padding: '8px 12px', height: 32 }}
            />
            <ActionLink>Browse…</ActionLink>
          </Field>
          <Field label="Accent">
            <AccentPicker value={p.color} onChange={() => {}} />
          </Field>
        </Section>

        {/* Services ───────────────────────────────────────────────────── */}
        <Section label="Services">
          <Field label="Subsystems">
            <div className="row row-gap" style={{ gap: 6, flexWrap: 'wrap' }}>
              {subs.map(s => (
                <button
                  key={s}
                  onClick={() => toggleSub(s)}
                  className={'pill is-' + subsState[s]}
                  style={{ cursor: 'pointer' }}
                >● {s}</button>
              ))}
            </div>
          </Field>
          <Field label="Email">
            <div className="row row-gap" style={{ gap: 6, flexWrap: 'wrap' }}>
              {emailAccounts.map(g => (
                <button
                  key={g}
                  onClick={() => toggleEmail(g)}
                  className={'pill is-' + emailState[g]}
                  style={{ cursor: 'pointer' }}
                >● {g}</button>
              ))}
            </div>
          </Field>
        </Section>

        {/* ALP ────────────────────────────────────────────────────────── */}
        <Section label="ALP (Alpi Link Protocol)">
          <Field label="Pubkey">
            <code className="mono" style={{
              fontSize: 12, color: 'var(--ink-2)',
              padding: '4px 8px', borderRadius: 6,
              background: 'var(--hover)',
              fontFamily: 'var(--font-mono)',
            }}>c+DTjH07Ok59ihEa22SD3YVpmM3+PiryoQfCQLsw9hs=</code>
            <ActionLink><span className="row row-gap" style={{ gap: 4 }}><window.I.Copy style={{ width:12, height:12 }} /> Copy</span></ActionLink>
          </Field>
          <Field label="Identity" align="top">
            <div className="col" style={{ flex: 1, gap: 6 }}>
              <textarea
                value={identity}
                onChange={e => { setIdentity(e.target.value); setIdentityDirty(true); }}
                placeholder="public identity — visible to peers"
                className="field"
                style={{ minHeight: 64, fontSize: 13, lineHeight: 'var(--lh-normal)' }}
              />
            </div>
            {identityDirty && (
              <div className="row row-gap" style={{ gap: 6, alignSelf: 'flex-start', paddingTop: 4 }}>
                <span className="tag" style={{ color: '#a98113', background: 'color-mix(in srgb, #d4b443 18%, var(--bg-pane))' }}>draft</span>
                <ActionLink onClick={() => { setIdentity(p.identity || ''); setIdentityDirty(false); }}>Discard</ActionLink>
                <ActionLink onClick={() => setIdentityDirty(false)}>Save</ActionLink>
              </div>
            )}
          </Field>
          <Field label="Port">
            <span className="pill is-on">● unix</span>
            <button
              className={'pill ' + (tcpOn ? 'is-on' : 'is-off')}
              style={{ cursor: 'pointer' }}
              onClick={() => setTcpOn(v => !v)}
            >● tcp {tcpOn ? 'on' : 'off'}</button>
          </Field>
          <Field label="Peers">
            <Popped trigger={<span>{peerCount} peer{peerCount !== 1 ? 's' : ''} · <span style={{ color: 'var(--ink-2)' }}>{onlineCount} online</span></span>} width={380}>
              {() => <window.PeersFlow peers={peers.length ? peers : [
                { id: 'alpi',   pubkey: 'pZ91Lm/8onlinepublickey0123', status: 'connected', allow: ['link.ping', 'link.ask'] },
                { id: 'doc',    pubkey: '7nQ3xK/2onlinepublickey0123', status: 'connected', allow: ['link.ping', 'link.ask'] },
                { id: 'echo',   pubkey: 'Kz7/WpdbwJ7Hc0QQ4ptBifs0kN7+q3hT9QXjqgMpNIM=', status: 'connected', allow: ['link.ping', 'link.ask'] },
                { id: 'ledger', pubkey: 'W1FLuHmpae5bTr0KDbKgH1toBQMGVeLxr0dhbD3nnJM=', status: 'connected', allow: ['link.ping', 'link.ask'] },
                { id: 'lex',    pubkey: 'uE19wThYu535kTxnomxpubkey0xxx', status: 'connected', allow: ['link.ping'] },
                { id: 'prism',  pubkey: 'Vx+7whnrtGuRMRl2omxpubkey0xxx', status: 'connected', allow: ['link.ping', 'link.ask'] },
                { id: 'zeta',   pubkey: 's8KylXdY8kXpo4Tuomxpubkey0xxx', status: 'connected', allow: ['link.ping', 'link.ask'] },
              ]} />}
            </Popped>
            <Popped mode="action" trigger="+ Add peer" width={420}>
              {({ close }) => <window.AddPeerPopover onClose={close} />}
            </Popped>
            <Popped trigger="1 pending invite" width={420}>
              {({ close }) => <window.PendingInvitesPopover onClose={close} />}
            </Popped>
          </Field>
          <Field label="Workgroups">
            <Popped trigger="1 workgroup" width={340}>
              {() => <window.WorkgroupPeersPopover items={[
                { id: 'archive', pubkey: '8ue607ioGA3JXNcJ' },
                { id: 'atlas',   pubkey: 'm0zfwor1P0c+LSDM' },
                { id: 'echo',    pubkey: 'Kz7/WpdbwJ7Hc0QQ' },
                { id: 'ledger',  pubkey: 'W1FLuHmpae5bTr0K' },
                { id: 'lex',     pubkey: 'uE19wThYu535kTxn' },
                { id: 'prism',   pubkey: 'Vx+7whnrtGuRMRl2' },
                { id: 'zeta',    pubkey: 's8KylXdY8kXpo4Tu' },
              ]} />}
            </Popped>
          </Field>
        </Section>

        {/* Devices ────────────────────────────────────────────────────── */}
        <Section label="Devices">
          <Field label="Paired">
            <Popped trigger={<span>5 devices · <span style={{ color: 'var(--ink-2)' }}>2 active</span></span>} width={340}>
              {() => <window.DevicesFlow devices={[
                { id: 'phone',  kind: 'phone',  label: 'Phone',         pubkey: 'JTniPmI5xxx', status: 'active' },
                { id: 'mbp',    kind: 'laptop', label: 'MacBook Pro',   pubkey: 'uea4DuGDxxx', status: 'active' },
                { id: 'office', kind: 'laptop', label: 'Office laptop', pubkey: 'Hi_zmAWlxxx', status: 'paired' },
                { id: 'demo',   kind: 'laptop', label: 'Demo device',   pubkey: 'BH8sbNzKxxx', status: 'paired' },
                { id: 'tablet', kind: 'tablet', label: 'Tablet',        pubkey: 'E2ivON10xxx', status: 'paired' },
              ]} />}
            </Popped>
            <ActionLink onClick={() => setPairOpen(true)}>+ Add device</ActionLink>
          </Field>
        </Section>

        {/* Schedule ───────────────────────────────────────────────────── */}
        <Section label="Schedule">
          <div className="col" style={{ gap: 2, marginTop: -4 }}>
            {schedule.map(s => <ScheduleRow key={s.id} s={s} />)}
          </div>
        </Section>

        {/* Sandbox ────────────────────────────────────────────────────── */}
        <Section label="Sandbox" kicker="filesystem fence · ⓘ">
          <Field label="Terminal">
            <span className={'pill ' + (terminal ? 'is-on' : 'is-off')}>● {terminal ? 'on' : 'off'}</span>
            <ActionLink onClick={() => setTerminal(v => !v)}>{terminal ? 'Disable' : 'Enable'}</ActionLink>
          </Field>
          <Field label="Network">
            <span className={'pill ' + (network ? 'is-on' : 'is-off')}>● {network ? 'on' : 'n/a'}</span>
            <ActionLink onClick={() => setNetwork(v => !v)}>{network ? 'Disable' : 'Allow'}</ActionLink>
          </Field>
        </Section>

        {/* Voice ──────────────────────────────────────────────────────── */}
        <Section label="Voice">
          <Field label="Voice">
            <Popped trigger={`${voice.name} · ${voice.locale} · ${voice.gender}`} width={300}>
              {({ close }) => <window.VoicePickerPopover value={voiceId} onChange={(id) => { setVoiceId(id); close(); }} />}
            </Popped>
            <ActionLink>Test</ActionLink>
          </Field>
        </Section>

        {/* MCP Servers ───────────────────────────────────────────────── */}
        <Section label="MCP Servers">
          <Field label="MCPs">
            <span style={{ color: 'var(--ink-3)', fontSize: 13 }}>none</span>
            <ActionLink onClick={() => setMcpOpen(true)}>+ Add MCP</ActionLink>
          </Field>
        </Section>

        {/* Skills ────────────────────────────────────────────────────── */}
        <Section label="Skills">
          <Field label="Personal">
            {skills.length === 0 ? (
              <span style={{ color: 'var(--ink-3)', fontSize: 13 }}>none</span>
            ) : (
              <div className="row row-gap" style={{ gap: 6, flexWrap: 'wrap' }}>
                {skills.map(s => (
                  <button
                    key={s}
                    onClick={() => ui.openPanel('skills')}
                    className="pill"
                    style={{ background: 'var(--hover)', color: 'var(--ink-2)', cursor: 'pointer' }}
                  >{s}</button>
                ))}
              </div>
            )}
            <ActionLink onClick={() => ui.openPanel('skills')}>Manage…</ActionLink>
          </Field>
        </Section>

        {/* Storage ───────────────────────────────────────────────────── */}
        <Section label="Storage">
          <Field label="Sessions">
            <span className="pill" style={{ background: 'var(--hover)' }}>385 KB</span>
            <span className="pill" style={{ background: 'var(--hover)' }}>6 files</span>
            <ActionLink>Reveal</ActionLink>
          </Field>
          <Field label="Logs">
            <span className="pill" style={{ background: 'var(--hover)' }}>23 KB</span>
            <span className="pill" style={{ background: 'var(--hover)' }}>2 files</span>
            <ActionLink>Reveal</ActionLink>
          </Field>
        </Section>

        {/* Danger Zone ────────────────────────────────────────────────── */}
        <Section label="Danger Zone">
          <Field label="Delete">
            <ActionLink danger onClick={() => setDeleteOpen(true)}>Delete profile</ActionLink>
            <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>
              removes <code className="mono" style={{ fontSize: 11 }}>~/.alpi/profiles/{p.id}/</code> — daemon picks up the change on its next restart
            </span>
          </Field>
        </Section>
      </div>

      {pairOpen && <window.PairDeviceFlow open={pairOpen} onClose={() => setPairOpen(false)} />}
      {mcpOpen && <window.AddMCPModal open={mcpOpen} onClose={() => setMcpOpen(false)} />}
      {providersOpen && <window.ProvidersModal open={providersOpen} onClose={() => setProvidersOpen(false)} />}
      <window.ConfirmDelete
        mode="typed"
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={`Delete profile @${p.id}`}
        consequence={<>This removes <code className="mono" style={{ fontSize: 12, background: 'var(--hover)', padding: '1px 5px', borderRadius: 4 }}>~/.alpi/profiles/{p.id}/</code> from disk: identity, memory, skills, schedule, and full session history. This action <strong>cannot be undone</strong>.</>}
        typeToConfirm={p.id}
        confirmLabel="Delete profile"
      />
    </div>
  );
}

// ── Workgroup detail (kept same flat-form pattern) ───────────────────────
function ScheduleRow({ s }) {
  const [confirm, setConfirm] = useStateS(false);
  const [enabled, setEnabled] = useStateS(s.on !== false);
  const [hover, setHover] = useStateS(false);
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'grid',
        gridTemplateColumns: '88px 168px 1fr auto',
        gap: 16, padding: '14px 0',
        borderTop: '.5px solid var(--line)',
        alignItems: 'center',
      }}
    >
      <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)', letterSpacing: '.02em' }}>{s.id}</span>
      <span
        className={'pill ' + (enabled ? 'is-on' : 'is-off')}
        style={{ fontFamily: 'var(--font-mono)', fontSize: 11, justifySelf: 'start' }}
      >● {s.cron}</span>
      <span style={{
        fontSize: 13, color: enabled ? 'var(--ink-2)' : 'var(--ink-4)',
        fontFamily: s.desc.startsWith('python3') ? 'var(--font-mono)' : 'inherit',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        minWidth: 0,
      }}>{s.desc}</span>
      <div className="row" style={{
        gap: 12, flexShrink: 0, position: 'relative',
        opacity: hover || confirm ? 1 : 0,
        transition: 'opacity .12s var(--ease)',
        pointerEvents: hover || confirm ? 'auto' : 'none',
      }}>
        <ActionLink>Fire</ActionLink>
        <ActionLink onClick={() => setEnabled(v => !v)}>{enabled ? 'Disable' : 'Enable'}</ActionLink>
        <span style={{ position: 'relative' }}>
          <ActionLink danger onClick={() => setConfirm(true)}>Delete</ActionLink>
          <window.ConfirmDelete
            mode="simple"
            open={confirm}
            onClose={() => setConfirm(false)}
            title={`Delete schedule ${s.id}?`}
            consequence="The job stops firing. You can recreate it later."
          />
        </span>
      </div>
    </div>
  );
}

function MemberRow({ member, isHub, note }) {
  const [confirm, setConfirm] = useStateS(false);
  return (
    <div className="row" style={{
      gap: 16, padding: '14px 0',
      borderTop: '.5px solid var(--line)',
      alignItems: 'flex-start',
    }}>
      <div className="col" style={{ width: 130, gap: 2, flexShrink: 0 }}>
        <div className="row row-gap" style={{ gap: 6 }}>
          <span className="diamond" style={{ '--c': member.color }} />
          <span className="mono" style={{ fontWeight: 600, fontSize: 13 }}>@{member.id}</span>
        </div>
        {isHub && <span className="mono" style={{ fontSize: 11, color: 'var(--ink-4)', letterSpacing: '.04em', textTransform: 'uppercase', marginLeft: 15 }}>hub</span>}
      </div>
      <p style={{ margin: 0, flex: 1, fontSize: 13, color: 'var(--ink-2)', lineHeight: 'var(--lh-normal)' }}>{note}</p>
      {!isHub && (
        <span style={{ position: 'relative' }}>
          <window.Tip text="Remove from workgroup" side="l">
            <button className="iconbtn" onClick={() => setConfirm(true)}><window.I.X /></button>
          </window.Tip>
          <window.ConfirmDelete
            mode="simple"
            open={confirm}
            onClose={() => setConfirm(false)}
            title={`Remove @${member.id}?`}
            consequence="They lose access to this workgroup. Their copy of the thread stays intact."
            confirmLabel="Remove"
          />
        </span>
      )}
    </div>
  );
}

function WorkgroupDetail({ id, state, ui }) {
  const w = window.MOCK.WORKGROUPS.find(x => x.id === id);
  if (!w) return null;
  const PROFILES = window.MOCK.PROFILES;
  const hub = PROFILES.find(p => p.id === w.hub);
  const [status, setStatus] = useStateS(w.status);
  const [briefing, setBriefing] = useStateS(w.briefing);
  const [briefingDirty, setBriefingDirty] = useStateS(false);
  const [budget, setBudget] = useStateS(w.budget.cap);
  const [deleteOpen, setDeleteOpen] = useStateS(false);
  const pct = (w.budget.used / budget) * 100;

  return (
    <div className="scroll" style={{ height: '100%', minWidth: 0 }}>
      {/* Hero */}
      <div style={{
        padding: 'var(--hero-pad-top) var(--pane-pad-x) var(--hero-pad-bottom)',
        borderBottom: '.5px solid var(--line)',
        position: 'sticky',
        top: 0,
        zIndex: 5,
        background: 'var(--bg-pane)',
      }}>
        <div className="row between" style={{ alignItems: 'flex-end' }}>
          <div className="col" style={{ gap: 8, flex: 1, minWidth: 0 }}>
            <div className="row row-gap" style={{ gap: 12 }}>
              <span className="hash" style={{ fontSize: 28, fontWeight: 500, color: 'var(--ink-4)', lineHeight: 'var(--lh-tight)' }}>#</span>
              <h1 className="display" style={{
                margin: 0, fontSize: 28, fontWeight: 'var(--display-weight)',
                fontStyle: 'var(--display-italic)', color: 'var(--ink)',
                }}>{w.id}</h1>
              <span className="mono" style={{ color: 'var(--ink-4)', fontSize: 11, marginLeft: 2, alignSelf: 'flex-end', paddingBottom: 4 }}>
                workgroup · settings
              </span>
            </div>
            <div className="row row-gap" style={{ gap: 14, color: 'var(--ink-3)', fontSize: 12, flexWrap: 'wrap' }}>
              <span className="row row-gap" style={{ gap: 5 }}>
                <span style={{ color: 'var(--ink-4)' }}>hub</span>
                <span className="diamond" style={{ '--c': hub.color, width: 7, height: 7 }} />
                <span className="mono" style={{ color: 'var(--ink-2)' }}>@{hub.id}</span>
              </span>
              <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
              <span><span style={{ color: 'var(--ink-4)' }}>members</span> <span className="mono tnum" style={{ color: 'var(--ink-2)' }}>{w.members.length}</span></span>
              <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
              <span className="row row-gap" style={{ gap: 5 }}>
                <span className="dot pulse-dot" style={{ '--c': status === 'paused' ? '#d4b443' : '#3fb37a', width: 6, height: 6 }} />
                <span style={{ color: 'var(--ink-2)' }}>{status}</span>
              </span>
              <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
              <span className="mono" style={{ color: 'var(--ink-3)' }}>wg_e3oo5l2srlo7qtlu</span>
            </div>
          </div>
          <div className="row row-gap" style={{ gap: 4 }}>
            <window.Tip text={status === 'paused' ? 'Resume workgroup' : 'Pause workgroup'} side="r">
              <button className="iconbtn" onClick={() => setStatus(s => s === 'active' ? 'paused' : 'active')}>
                {status === 'paused' ? <window.I.Play /> : <window.I.Pause />}
              </button>
            </window.Tip>
            <window.Tip text="Back to chat · ⌘," side="r">
              <button className="iconbtn" onClick={() => ui.openChat({ kind: 'workgroup', id: w.id })}>
                <window.I.ArrowLeft />
              </button>
            </window.Tip>
          </div>
        </div>
        <span style={{
          position: 'absolute', left: 32, bottom: -0.5, height: 1.5,
          width: 40, background: w.color,
        }} />
      </div>

      {/* Body */}
      <div style={{ padding: 'var(--space-9) var(--pane-pad-x) 80px', maxWidth: 920, width: '100%', margin: '0 auto' }}>
        <Section label="Overview">
          <Field label="Hub">
            <div className="row row-gap" style={{ gap: 8 }}>
              <span className="diamond" style={{ '--c': hub.color }} />
              <span className="mono" style={{ fontSize: 13 }}>@{hub.id}</span>
            </div>
          </Field>
          <Field label="Status">
            <span className={'pill ' + (status === 'paused' ? 'is-off' : 'is-on')}>● {status}</span>
            <ActionLink onClick={() => setStatus(s => s === 'active' ? 'paused' : 'active')}>
              {status === 'paused' ? 'Resume' : 'Pause'}
            </ActionLink>
          </Field>
          <Field label="ID">
            <span className="mono" style={{ fontSize: 12, color: 'var(--ink-2)' }}>wg_e3oo5l2srlo7qtlu</span>
            <ActionLink><span className="row row-gap" style={{ gap: 4 }}><window.I.Copy style={{ width:12, height:12 }} /> Copy</span></ActionLink>
          </Field>
        </Section>

        <Section label="Budget" kicker="workgroup spend cap">
          <Field label="Used" align="top">
            <div className="col" style={{ flex: 1, gap: 8 }}>
              <div className="row row-gap" style={{ gap: 12, alignItems: 'baseline' }}>
                <div className="display tnum" style={{ fontSize: 28 }}>${w.budget.used.toFixed(2)}</div>
                <div className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                  of <span className="tnum" style={{ color: 'var(--ink-2)' }}>${budget.toFixed(2)}</span> · {Math.round(pct)}%
                </div>
                <span style={{ flex: 1 }} />
                <Popped mode="action" trigger="Edit cap" width={260} align="right">
                  {({ close }) => (
                    <window.BudgetEditPopover
                      value={budget}
                      usdOnly={true}
                      onSave={({ amount }) => { setBudget(amount); close(); }}
                    />
                  )}
                </Popped>
              </div>
              <div style={{ width: '100%', height: 6, background: 'var(--line)', borderRadius: 999, overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(100, pct)}%`, height: '100%', background: w.color, borderRadius: 999, transition: 'width .3s' }} />
              </div>
            </div>
          </Field>
        </Section>

        <Section label="Briefing" kicker="what this workgroup decides">
          <Field label="Brief" align="top">
            <div className="col" style={{ flex: 1, gap: 6 }}>
              <textarea
                value={briefing}
                onChange={e => { setBriefing(e.target.value); setBriefingDirty(true); }}
                className="field"
                style={{ minHeight: 120, lineHeight: 'var(--lh-normal)', fontSize: 13 }}
              />
            </div>
            {briefingDirty && (
              <div className="row row-gap" style={{ gap: 6, alignSelf: 'flex-start', paddingTop: 4 }}>
                <span className="tag" style={{ color: '#a98113', background: 'color-mix(in srgb, #d4b443 18%, var(--bg-pane))' }}>draft</span>
                <ActionLink onClick={() => { setBriefing(w.briefing); setBriefingDirty(false); }}>Discard</ActionLink>
                <ActionLink onClick={() => setBriefingDirty(false)}>Save</ActionLink>
              </div>
            )}
          </Field>
        </Section>

        <Section label="Members" kicker={`${w.members.length} alpis`}>
          <div className="col" style={{ gap: 0, marginTop: -4 }}>
            {/* Sort: hub first, then alphabetical */}
            {[...w.members].sort((a, b) => (a === w.hub ? -1 : b === w.hub ? 1 : a.localeCompare(b))).map(mid => {
              const m = PROFILES.find(p => p.id === mid);
              if (!m) return null;
              const note = window.MOCK.ROADMAP_MEMBER_NOTES[mid] || m.identity || `${mid} — no description.`;
              const isHub = mid === w.hub;
              return <MemberRow key={mid} member={m} isHub={isHub} note={note} />;
            })}
            <div style={{ marginTop: 4 }}>
              <Popped mode="action" trigger="+ Add member" width={340}>
                {({ close }) => <window.AddMemberPopover candidates={[
                  { id: 'atlas',  pubkey: 'm0zfwor1P0c+LSDM' },
                  { id: 'canvas', pubkey: 'M6ehYeYaDKaliTTY' },
                  { id: 'fern',   pubkey: 'PDvgdhyCi9/ZYOSp' },
                  { id: 'ledger', pubkey: 'W1FLuHmpae5bTr0K' },
                  { id: 'lumen',  pubkey: 'PZ91Lm8onlinepb' },
                ]} onPick={close} />}
              </Popped>
            </div>
          </div>
        </Section>

        <Section label="Danger Zone">
          <Field label="Delete">
            <ActionLink danger onClick={() => setDeleteOpen(true)}>Delete workgroup</ActionLink>
            <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>
              Removes the channel and all history. Members keep their own copies.
            </span>
          </Field>
        </Section>
      </div>

      <window.ConfirmDelete
        mode="typed"
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={`Delete workgroup #${w.id}`}
        consequence={<>This removes the channel and all thread history, tasks, and decisions. Members keep their own copies of past messages. This action <strong>cannot be undone</strong>.</>}
        typeToConfirm={w.id}
        confirmLabel="Delete workgroup"
      />
    </div>
  );
}

function SettingsView({ state, ui }) {
  return (
    <div style={{ height: '100%', minWidth: 0 }}>
      {state.settingsTarget.kind === 'profile'
        ? <ProfileDetail id={state.settingsTarget.id} state={state} ui={ui} />
        : <WorkgroupDetail id={state.settingsTarget.id} state={state} ui={ui} />
      }
    </div>
  );
}

window.SettingsView = SettingsView;
