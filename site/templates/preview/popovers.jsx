// popovers.jsx — settings popovers + modals
// All reuse the same shells: anchored popover (right of trigger) vs centered modal w/ scrim.

const { useState: useStateP, useRef: useRefP, useEffect: useEffectP } = React;

// ── Generic anchored popover (closes on outside click) ───────────────────
function Anchored({ open, onClose, children, width = 320, align = 'left' }) {
  const ref = useRefP(null);
  useEffectP(() => {
    if (!open) return;
    const onDoc = (e) => { if (!ref.current?.contains(e.target)) onClose(); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      ref={ref}
      className="anim-pop"
      style={{
        position: 'absolute', top: 'calc(100% + 6px)',
        [align]: 0, width,
        background: 'var(--bg-elev)', border: '.5px solid var(--line-2)',
        borderRadius: 12, boxShadow: 'var(--shadow)',
        zIndex: 30, overflow: 'hidden',
      }}
    >{children}</div>
  );
}

// ── Modal shell — scrim + centered sheet ─────────────────────────────────
function Modal({ open, onClose, title, children, width = 440 }) {
  if (!open) return null;
  return (
    <div
      className="anim-fade"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: 'absolute', inset: 0,
        background: 'color-mix(in srgb, var(--ink) 18%, transparent)',
        backdropFilter: 'blur(2px)',
        zIndex: 80,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div className="anim-pop col" style={{
        width, maxWidth: 'calc(100vw - 80px)', maxHeight: 'calc(100vh - 80px)',
        background: 'var(--bg-elev)', borderRadius: 16,
        border: '.5px solid var(--line-2)', boxShadow: 'var(--shadow)',
        padding: 24, gap: 16, overflowY: 'auto',
      }}>
        {title && (
          <div className="row between">
            <strong style={{ fontSize: 15 }}>{title}</strong>
            <window.Tip text="Close" side="r"><button className="iconbtn" onClick={onClose}><window.I.X /></button></window.Tip>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

// ── Form label ───────────────────────────────────────────────────────────
function FLabel({ children }) {
  return <label className="eyebrow" style={{ display: 'block', marginBottom: 6 }}>{children}</label>;
}

// ── PeersFlow — list → detail (drill in/out) ────────────────────────────
function PeersFlow({ peers }) {
  const [selected, setSelected] = useStateP(null);
  if (selected) {
    return (
      <PeerDetailPopover
        peer={selected}
        onClose={() => setSelected(null)}
        onRemove={() => setSelected(null)}
      />
    );
  }
  return <PeersListPopover peers={peers} onPick={setSelected} />;
}

// ── PeersPopover — list of peers with online/offline status ──────────────
function PeersListPopover({ peers, onPick, onAdd }) {
  return (
    <div className="col" style={{ padding: 6 }}>
      {peers.map(pe => {
        const peerP = window.MOCK.PROFILES.find(pp => pp.id === pe.id);
        const online = pe.status ? pe.status === 'connected' : pe.lastSeen === 'now' || pe.lastSeen === '1h ago';
        return (
          <button
            key={pe.id}
            onClick={() => onPick?.(pe)}
            className="row"
            style={{
              padding: '8px 10px', borderRadius: 8, gap: 10,
              textAlign: 'left', alignItems: 'center',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            {peerP && <span className="diamond" style={{ '--c': peerP.color, width: 9, height: 9 }} />}
            <div className="col" style={{ flex: 1, gap: 1 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)' }}>{pe.label || pe.id}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>…{pe.pubkey.slice(-7)}</span>
            </div>
            <span className={'pill ' + (online ? 'is-on' : 'is-off')} style={{ flexShrink: 0 }}>● {online ? 'online' : 'offline'}</span>
          </button>
        );
      })}
    </div>
  );
}

// ── PeerDetailPopover — selected peer detail ────────────────────────────
function PeerDetailPopover({ peer, onClose, onRemove }) {
  const peerP = peer && window.MOCK.PROFILES.find(pp => pp.id === peer.id);
  if (!peer) return null;
  const status = peer.status || 'connected';
  return (
    <div className="col" style={{ padding: 16, gap: 12 }}>
      <div className="col" style={{ gap: 4 }}>
        <FLabel>Peer</FLabel>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500 }}>@{peer.id}</span>
      </div>
      <div className="col" style={{ gap: 4 }}>
        <FLabel>Status</FLabel>
        <span className={'pill ' + (status === 'connected' ? 'is-on' : 'is-off')} style={{ alignSelf: 'flex-start' }}>● {status === 'connected' ? 'online' : status}</span>
      </div>
      <div className="col" style={{ gap: 4 }}>
        <FLabel>Pubkey</FLabel>
        <code className="mono" style={{ fontSize: 11, color: 'var(--ink-2)', wordBreak: 'break-all' }}>{peer.pubkey}</code>
      </div>
      <div className="col" style={{ gap: 4 }}>
        <FLabel>Allow</FLabel>
        <div className="row row-gap" style={{ gap: 6, flexWrap: 'wrap' }}>
          {(peer.allow || ['link.ping', 'link.ask']).map(s => <span key={s} className="pill is-on">● {s}</span>)}
        </div>
      </div>
      <div className="row between" style={{ marginTop: 4 }}>
        <button className="alink" onClick={onClose}>Close</button>
        <button className="alink danger" onClick={() => { onRemove?.(); onClose(); }}>Remove peer</button>
      </div>
    </div>
  );
}

// ── AddPeerPopover ───────────────────────────────────────────────────────
function AddPeerPopover({ onClose }) {
  return (
    <div className="col" style={{ padding: 16, gap: 12 }}>
      <div><FLabel>ID</FLabel><input className="field" placeholder="peer handle (a-z, 0-9, -, _)" /></div>
      <div><FLabel>Pubkey</FLabel><textarea className="field field-mono" placeholder="base64 ed25519 pubkey" rows={2} style={{ minHeight: 56 }} /></div>
      <div><FLabel>Address (optional)</FLabel><input className="field field-mono" placeholder="host:port — leave empty for intra-machine" /></div>
      <div><FLabel>Alias (optional)</FLabel><input className="field" placeholder="display label" /></div>
      <div>
        <FLabel>Allow</FLabel>
        <div className="row row-gap" style={{ gap: 6, flexWrap: 'wrap' }}>
          {['link.ping', 'link.ask', 'link.cancel'].map(s => <span key={s} className="pill is-on">● {s}</span>)}
        </div>
      </div>
      <div className="row between">
        <button className="alink" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={onClose}>Add peer</button>
      </div>
    </div>
  );
}

// ── PendingInvitesPopover ────────────────────────────────────────────────
function PendingInvitesPopover({ invites = [], onClose }) {
  const list = invites.length ? invites : [{ id: 'kz7-wpd', pubkey: 'Kz7/WpdbwJ7Hc0QQ...', note: 'first contact' }];
  return (
    <div className="col" style={{ padding: 10, gap: 6 }}>
      {list.map(i => (
        <div key={i.id} className="row" style={{ gap: 10, padding: '8px 10px', borderRadius: 8 }}>
          <div className="col" style={{ flex: 1, gap: 2 }}>
            <span className="mono" style={{ fontSize: 12, color: 'var(--ink)' }}>{i.pubkey}</span>
            <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>
              <span className="mono">{i.pubkey.slice(0, 18)}…</span>
              <span style={{ margin: '0 4px' }}>·</span>
              <span>{i.note}</span>
            </span>
          </div>
          <button className="btn btn-primary" style={{ height: 26, fontSize: 12 }}>Accept</button>
          <button className="alink">Discard</button>
        </div>
      ))}
    </div>
  );
}

// ── WorkgroupsPopover — list of @ profiles with online status ────────────
function WorkgroupPeersPopover({ items, onClose }) {
  return (
    <div className="col" style={{ padding: 8 }}>
      {items.map(p => {
        const prof = window.MOCK.PROFILES.find(pp => pp.id === p.id);
        return (
          <button
            key={p.id}
            className="row row-gap"
            style={{ padding: '8px 10px', borderRadius: 8, gap: 10, textAlign: 'left' }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <span className="dot" style={{ '--c': prof?.color, width: 9, height: 9 }} />
            <div className="col" style={{ flex: 1, gap: 1 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--ink)' }}>@{p.id}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{p.pubkey?.slice(0, 18) || ''}…</span>
            </div>
            <span className="pill is-on">● online</span>
          </button>
        );
      })}
    </div>
  );
}

// ── VoicePicker — list of voices ─────────────────────────────────────────
const VOICES = [
  { id: 'aria',   name: 'Aria',   locale: 'English (US)',  gender: 'female' },
  { id: 'guy',    name: 'Guy',    locale: 'English (US)',  gender: 'male' },
  { id: 'sonia',  name: 'Sonia',  locale: 'English (UK)',  gender: 'female' },
  { id: 'alvaro', name: 'Alvaro', locale: 'Spanish (ES)',  gender: 'male' },
  { id: 'elvira', name: 'Elvira', locale: 'Spanish (ES)',  gender: 'female' },
  { id: 'dalia',  name: 'Dalia',  locale: 'Spanish (MX)',  gender: 'female' },
  { id: 'denise', name: 'Denise', locale: 'French',        gender: 'female' },
  { id: 'katja',  name: 'Katja',  locale: 'German',        gender: 'female' },
];

function VoicePickerPopover({ value, onChange }) {
  return (
    <div className="col" style={{ padding: 6, maxHeight: 360, overflowY: 'auto' }}>
      {VOICES.map(v => {
        const sel = v.id === value;
        return (
          <button
            key={v.id}
            onClick={() => onChange?.(v.id)}
            className="col"
            style={{
              padding: '8px 12px', borderRadius: 8, gap: 2,
              textAlign: 'left', background: sel ? 'var(--selected)' : 'transparent',
            }}
            onMouseEnter={e => { if (!sel) e.currentTarget.style.background = 'var(--hover)'; }}
            onMouseLeave={e => { if (!sel) e.currentTarget.style.background = 'transparent'; }}
          >
            <span style={{ fontSize: 13, fontWeight: sel ? 600 : 500 }}>{v.name}</span>
            <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>{v.locale} · {v.gender}</span>
          </button>
        );
      })}
    </div>
  );
}

// ── BudgetEditPopover ───────────────────────────────────────────────────
function BudgetEditPopover({ value, onSave, usdOnly = false }) {
  const [type, setType] = useStateP('USD');
  const [amount, setAmount] = useStateP(value || 2);
  return (
    <div className="col" style={{ padding: 14, gap: 12 }}>
      {!usdOnly && (
        <div className="col" style={{ gap: 5 }}>
          <FLabel>Cap type</FLabel>
          <div className="row row-gap" style={{ gap: 6 }}>
            <button className={'pill ' + (type === 'USD' ? 'is-on' : 'is-off')} onClick={() => setType('USD')}>● USD</button>
            <button className={'pill ' + (type === 'tokens' ? 'is-on' : 'is-off')} onClick={() => setType('tokens')}>● tokens</button>
          </div>
        </div>
      )}
      <div>
        <FLabel>{usdOnly ? 'Daily USD cap' : (type === 'USD' ? 'Daily USD' : 'Daily tokens')}</FLabel>
        <input
          type="number" value={amount}
          onChange={e => setAmount(+e.target.value)}
          className="field field-mono" style={{ fontSize: 14 }}
          autoFocus
        />
      </div>
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={() => onSave?.({ type: usdOnly ? 'USD' : type, amount })}>Save</button>
      </div>
    </div>
  );
}

// ── PairDeviceFlow — Label step → QR step ────────────────────────────────
// ── PairDeviceFlow — single modal: label + QR side-by-side ───────────────
function PairDeviceFlow({ open, onClose }) {
  const [label, setLabel] = useStateP('');

  useEffectP(() => { if (open) setLabel(''); }, [open]);

  if (!open) return null;

  const hasLabel = label.trim().length > 0;
  const slug = (label.trim() || 'device').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');

  return (
    <Modal open={open} onClose={onClose} width={520} title={null}>
      <strong style={{ fontSize: 15 }}>Pair a new device</strong>

      <div>
        <FLabel>Label</FLabel>
        <input
          autoFocus
          value={label}
          onChange={e => setLabel(e.target.value)}
          className="field"
          placeholder="MacBook Pro · Phone · …"
          onKeyDown={e => { if (e.key === 'Enter' && hasLabel) onClose(); }}
        />
      </div>

      {/* QR + token row */}
      <div className="row" style={{ gap: 18, alignItems: 'stretch' }}>
        {/* QR cell — placeholder until label exists */}
        <div style={{
          width: 184, height: 184, flexShrink: 0,
          background: '#fff', padding: 10, borderRadius: 8,
          border: '.5px solid var(--line-2)',
          position: 'relative',
          opacity: hasLabel ? 1 : 0.35,
          transition: 'opacity .22s var(--ease)',
        }}>
          {hasLabel ? (
            <QRPattern />
          ) : (
            <div className="col center" style={{ height: '100%', color: '#888', fontSize: 11, fontFamily: 'var(--font-mono)', textAlign: 'center', padding: 16, lineHeight: 1.4 }}>
              Type a label to generate
            </div>
          )}
        </div>

        {/* Right column — token info + helper */}
        <div className="col" style={{ flex: 1, gap: 10, justifyContent: 'center', minWidth: 0 }}>
          <div className="col" style={{ gap: 6 }}>
            <FLabel>Host</FLabel>
            <span className="mono" style={{ fontSize: 12, color: hasLabel ? 'var(--ink-2)' : 'var(--ink-4)' }}>
              100.114.140.25:49200
            </span>
          </div>
          <div className="col" style={{ gap: 6 }}>
            <FLabel>Token</FLabel>
            <span className="mono" style={{ fontSize: 12, color: hasLabel ? 'var(--ink-2)' : 'var(--ink-4)' }}>
              …0YTgrPOV
            </span>
          </div>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--ink-3)', lineHeight: 'var(--lh-normal)' }}>
            Scan with the Alpi app on the other device, or copy the link below.
          </p>
        </div>
      </div>

      {/* alpi:// link */}
      <div className="row" style={{
        gap: 6, padding: '8px 10px',
        background: 'var(--hover)', borderRadius: 8,
        fontFamily: 'var(--font-mono)', color: hasLabel ? 'var(--ink-2)' : 'var(--ink-4)',
        alignItems: 'center', fontSize: 11,
        opacity: hasLabel ? 1 : 0.6,
        transition: 'opacity .22s var(--ease)',
      }}>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
          alpi://device?v=2&host=100.114.140.25&port=49200&name={slug}&token=…
        </span>
        <button className="iconbtn" style={{ width: 22, height: 22 }} disabled={!hasLabel}>
          <window.I.Copy style={{ width: 12, height: 12 }} />
        </button>
      </div>

      <div className="row" style={{ justifyContent: 'flex-end', gap: 12 }}>
        <button className="alink" onClick={onClose}>Cancel</button>
        <button
          className="btn btn-primary"
          onClick={onClose}
          disabled={!hasLabel}
          style={{ opacity: hasLabel ? 1 : 0.4 }}
        >Pair</button>
      </div>
    </Modal>
  );
}

// ── AddMCPModal ──────────────────────────────────────────────────────────
function AddMCPModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Add MCP server" width={580}>
      <p style={{ margin: 0, fontSize: 12, color: 'var(--ink-3)', lineHeight: 'var(--lh-normal)' }}>
        Example — GitHub MCP: command <code className="mono" style={{ fontSize: 11, background: 'var(--hover)', padding: '1px 5px', borderRadius: 4 }}>npx</code>, args <code className="mono" style={{ fontSize: 11, background: 'var(--hover)', padding: '1px 5px', borderRadius: 4 }}>-y @modelcontextprotocol/server-github</code>, env <code className="mono" style={{ fontSize: 11, background: 'var(--hover)', padding: '1px 5px', borderRadius: 4 }}>GITHUB_TOKEN=ghp_…</code>.
      </p>
      <div><FLabel>Name</FLabel><input className="field" placeholder="github · notion · linear" /></div>
      <div><FLabel>Command</FLabel><input className="field field-mono" placeholder="npx · uvx · python · /path/to/server" /></div>
      <div><FLabel>Args</FLabel><input className="field field-mono" placeholder="space-separated · use quotes for grouping" /></div>
      <div>
        <FLabel>Env (key=value per line)</FLabel>
        <textarea className="field field-mono" rows={3} placeholder="GITHUB_TOKEN=ghp_xxx&#10;FOO=bar" />
      </div>
      <div className="row" style={{ justifyContent: 'flex-end', gap: 12 }}>
        <button className="alink" onClick={onClose}>Close</button>
        <button className="btn btn-primary">Add</button>
      </div>
    </Modal>
  );
}

// ── ProvidersModal ───────────────────────────────────────────────────────
const PROVIDER_TYPES = ['Ollama', 'Anthropic', 'OpenAI', 'OpenRouter', 'Gemini'];

function ProvidersModal({ open, onClose }) {
  const [picked, setPicked] = useStateP('Ollama');
  const configured = [
    { name: 'Anthropic', key: 'sk-…5QAA' },
    { name: 'OpenAI',    key: 'sk-…umYA' },
    { name: 'OpenRouter',key: 'sk-…d1e5' },
  ];
  return (
    <Modal open={open} onClose={onClose} title={null} width={520}>
      <div className="eyebrow">Configured</div>
      <div className="col" style={{ gap: 2 }}>
        {configured.map(p => (
          <div key={p.name} className="row" style={{ padding: '8px 4px', alignItems: 'baseline' }}>
            <span style={{ fontWeight: 600, fontSize: 13, flexShrink: 0 }}>{p.name}</span>
            <span style={{ color: 'var(--ink-4)', margin: '0 8px' }}>·</span>
            <span className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>{p.key}</span>
            <span style={{ flex: 1 }} />
            <button className="alink">Remove</button>
          </div>
        ))}
      </div>
      <div className="eyebrow">Add new</div>
      <div className="row row-gap" style={{ gap: 6, flexWrap: 'wrap' }}>
        {PROVIDER_TYPES.map(p => (
          <button key={p} className={'pill ' + (p === picked ? 'is-on' : 'is-off')} onClick={() => setPicked(p)}>● {p}</button>
        ))}
      </div>
      <div><FLabel>Name</FLabel><input className="field" placeholder="local · home-gpu · cloud-a" /></div>
      <div><FLabel>{picked === 'Ollama' ? 'URL' : 'API key'}</FLabel>
        <input className={picked === 'Ollama' ? 'field' : 'field field-mono'} placeholder={picked === 'Ollama' ? 'http://localhost:11434' : 'sk-…'} />
      </div>
      <div className="row" style={{ justifyContent: 'flex-end', gap: 12 }}>
        <button className="alink" onClick={onClose}>Close</button>
        <button className="btn btn-primary">Save</button>
      </div>
    </Modal>
  );
}

// ── QR pattern (deterministic) ───────────────────────────────────────────
function QRPattern() {
  const N = 21;
  const isOn = (i, j) => {
    const inFinder = (r, c) =>
      ((i >= r && i < r + 7) && (j >= c && j < c + 7) && (
        (i === r || i === r + 6 || j === c || j === c + 6) ||
        ((i >= r + 2 && i <= r + 4) && (j >= c + 2 && j <= c + 4))
      ));
    if (inFinder(0, 0) || inFinder(0, N - 7) || inFinder(N - 7, 0)) return true;
    const clearInside = (r, c) =>
      (i >= r && i < r + 7) && (j >= c && j < c + 7);
    if (clearInside(0, 0) || clearInside(0, N - 7) || clearInside(N - 7, 0)) return false;
    const seed = (i * 73856093) ^ (j * 19349663);
    return (seed & 7) > 2;
  };
  const cells = [];
  for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
    if (isOn(i, j)) cells.push({ i, j });
  }
  return (
    <svg viewBox={`0 0 ${N} ${N}`} style={{ width: '100%', height: '100%', shapeRendering: 'crispEdges' }}>
      {cells.map(({ i, j }, idx) => (
        <rect key={idx} x={j} y={i} width="1" height="1" fill="#000" />
      ))}
    </svg>
  );
}

// ── DevicesListPopover — list of paired devices ─────────────────────────
function DevicesListPopover({ devices, onPick }) {
  return (
    <div className="col" style={{ padding: 6 }}>
      {devices.map(d => (
        <button
          key={d.id}
          onClick={() => onPick?.(d)}
          className="row"
          style={{
            padding: '8px 10px', borderRadius: 8, gap: 10,
            textAlign: 'left', alignItems: 'center',
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'var(--hover)'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
        >
          <span style={{ width: 24, height: 24, borderRadius: 5, background: 'var(--bg-input)', border: '.5px solid var(--line)', display: 'grid', placeItems: 'center', color: 'var(--ink-2)' }}>
            {d.kind === 'phone'
              ? <svg viewBox="0 0 16 16" style={{ width: 12, height: 12, stroke: 'currentColor', fill: 'none', strokeWidth: 1.5 }}><rect x="5" y="2.5" width="6" height="11" rx="1.5"/><path d="M7 12h2"/></svg>
              : <window.I.Cpu />
            }
          </span>
          <div className="col" style={{ flex: 1, gap: 1 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)' }}>{d.label}</span>
            <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>…{d.pubkey.slice(-7)}</span>
          </div>
          <span className={'pill ' + (d.status === 'active' ? 'is-on' : 'is-off')} style={{ flexShrink: 0 }}>
            ● {d.status === 'active' ? 'active' : 'paired'}
          </span>
        </button>
      ))}
    </div>
  );
}

// ── DeviceDetailPopover — edit label / revoke a paired device ───────────
function DeviceDetailPopover({ device, onClose, onRevoke }) {
  const [label, setLabel] = useStateP(device?.label || '');
  if (!device) return null;
  return (
    <div className="col" style={{ padding: 16, gap: 12 }}>
      <div className="col" style={{ gap: 4 }}>
        <FLabel>Label</FLabel>
        <input
          className="field" value={label}
          onChange={e => setLabel(e.target.value)}
          autoFocus
        />
      </div>
      <div className="col" style={{ gap: 4 }}>
        <FLabel>Token id</FLabel>
        <span className="mono" style={{ fontSize: 12, color: 'var(--ink-2)' }}>…{device.pubkey.slice(-7)}</span>
      </div>
      <div className="col" style={{ gap: 4 }}>
        <FLabel>Last seen</FLabel>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{device.status === 'active' ? 'now' : 'never'}</span>
      </div>
      <div className="row between" style={{ marginTop: 4 }}>
        <button className="alink" onClick={onClose}>Close</button>
        <button className="alink danger" onClick={() => { onRevoke?.(device); onClose(); }}>Revoke</button>
      </div>
    </div>
  );
}

// ── DevicesFlow — list → detail ───────────────────────────────────────────
function DevicesFlow({ devices }) {
  const [selected, setSelected] = useStateP(null);
  if (selected) {
    return <DeviceDetailPopover device={selected} onClose={() => setSelected(null)} onRevoke={() => setSelected(null)} />;
  }
  return <DevicesListPopover devices={devices} onPick={setSelected} />;
}

// ── AddMemberPopover — picks a peer to add as workgroup member ───────────
function AddMemberPopover({ candidates, onPick }) {
  return (
    <div className="col" style={{ padding: 6 }}>
      {candidates.map((c, idx) => {
        const prof = window.MOCK.PROFILES.find(p => p.id === c.id);
        return (
          <button
            key={c.id}
            onClick={() => onPick?.(c)}
            className="row"
            style={{
              padding: '10px 12px', borderRadius: 8, gap: 12,
              textAlign: 'left', alignItems: 'center',
              background: idx === 0 ? 'var(--hover)' : 'transparent',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--hover)'}
            onMouseLeave={e => e.currentTarget.style.background = idx === 0 ? 'var(--hover)' : 'transparent'}
          >
            <span className="dot" style={{ '--c': prof?.color || 'var(--ink-3)', width: 9, height: 9 }} />
            <div className="col" style={{ flex: 1, gap: 1 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--ink)' }}>@{c.id}</span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{c.pubkey}…</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── ConfirmDelete — unified destructive confirmation ────────────────────
// mode 'simple'  → inline popover (reversible: kick member, delete schedule)
// mode 'typed'   → modal with type-to-confirm (irreversible: delete profile, delete workgroup)
function ConfirmDelete({ mode = 'simple', open, onClose, onConfirm, title, consequence, typeToConfirm, confirmLabel = 'Delete' }) {
  if (mode === 'simple') {
    return (
      <window.Anchored open={open} onClose={onClose} width={280} align="right">
        <div className="col" style={{ padding: 14, gap: 10 }}>
          <div className="col" style={{ gap: 4 }}>
            <strong style={{ fontSize: 13 }}>{title}</strong>
            <span style={{ fontSize: 12, color: 'var(--ink-3)', lineHeight: 'var(--lh-normal)' }}>{consequence}</span>
          </div>
          <div className="row" style={{ justifyContent: 'flex-end', gap: 12 }}>
            <button className="alink" onClick={onClose}>Cancel</button>
            <button className="alink danger" onClick={() => { onConfirm?.(); onClose?.(); }}>{confirmLabel}</button>
          </div>
        </div>
      </window.Anchored>
    );
  }
  // typed
  return <TypedConfirmModal open={open} onClose={onClose} onConfirm={onConfirm} title={title} consequence={consequence} typeToConfirm={typeToConfirm} confirmLabel={confirmLabel} />;
}

function TypedConfirmModal({ open, onClose, onConfirm, title, consequence, typeToConfirm, confirmLabel }) {
  const [typed, setTyped] = useStateP('');
  useEffectP(() => { if (open) setTyped(''); }, [open]);
  if (!open) return null;
  const matches = typed === typeToConfirm;
  return (
    <Modal open={open} onClose={onClose} title={null} width={440}>
      <div className="col" style={{ gap: 6 }}>
        <strong style={{ fontSize: 15, color: 'var(--c-danger)' }}>{title}</strong>
        <span style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 'var(--lh-normal)', textWrap: 'pretty' }}>{consequence}</span>
      </div>
      <div className="col" style={{ gap: 6 }}>
        <FLabel>
          Type <code className="mono" style={{ fontSize: 11, background: 'var(--hover)', padding: '1px 6px', borderRadius: 4, color: 'var(--ink)' }}>{typeToConfirm}</code> to confirm
        </FLabel>
        <input
          className="field field-mono"
          value={typed}
          onChange={e => setTyped(e.target.value)}
          autoFocus
        />
      </div>
      <div className="row" style={{ justifyContent: 'flex-end', gap: 12 }}>
        <button className="alink" onClick={onClose}>Cancel</button>
        <button
          disabled={!matches}
          onClick={() => { onConfirm?.(); onClose?.(); }}
          className="btn"
          style={{
            background: matches ? 'var(--c-danger)' : 'var(--line)',
            color: matches ? '#fff' : 'var(--ink-3)',
            cursor: matches ? 'pointer' : 'default',
          }}
        >{confirmLabel}</button>
      </div>
    </Modal>
  );
}

// ── New profile · minimal create modal ────────────────────────────────
const ACCENT_PALETTE = [
  '#b8954a','#d97757','#c14545','#c14580','#9d4dc6','#6a6dd6',
  '#3d7ea6','#2f8e9e','#2f7d6e','#3fb37a','#8a7a4a','#6c7480',
];

function NewProfileModal({ open, onClose, onCreate, onOpenProviders }) {
  const [name, setName] = useStateP('');
  const [model, setModel] = useStateP('openai/gpt-5.4-mini');
  // First-run path: when no providers are configured, replace ModelPicker with
  // an inline provider-create form. The user creates the first provider here.
  const providers = window.MOCK.PROVIDERS || [];
  const noProviders = providers.length === 0;
  const [provKind, setProvKind] = useStateP('Ollama');
  const [provName, setProvName] = useStateP('');
  const [provUrl, setProvUrl] = useStateP('');

  const nextAccent = () => {
    const used = new Set(window.MOCK.PROFILES.map(p => p.color.toLowerCase()));
    return ACCENT_PALETTE.find(c => !used.has(c.toLowerCase())) || ACCENT_PALETTE[0];
  };

  useEffectP(() => {
    if (open) {
      setName(''); setModel('openai/gpt-5.4-mini');
      setProvKind('Ollama'); setProvName(''); setProvUrl('');
    }
  }, [open]);

  if (!open) return null;
  const validName = /^[a-z0-9_-]{2,}$/i.test(name.trim());
  const slug = name.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
  const accent = nextAccent();
  // Provider validity: name 2+, plus URL (Ollama) OR key (others)
  const validProv = !noProviders || (provName.trim().length >= 2 && provUrl.trim().length > 0);
  const valid = validName && validProv;
  const urlLabel = provKind === 'Ollama' ? 'URL' : 'API key';
  const urlPlaceholder = provKind === 'Ollama' ? 'http://localhost:11434' : 'sk-…';

  return (
    <Modal open={open} onClose={onClose} title={null} width={520}>
      <strong style={{ fontSize: 15 }}>New profile</strong>

      <div>
        <FLabel>Name</FLabel>
        <input
          autoFocus
          value={name}
          onChange={e => setName(e.target.value)}
          className="field"
          placeholder="work · personal · home-server"
        />
        <div style={{ marginTop: 6, fontSize: 11.5, color: 'var(--ink-3)', lineHeight: 'var(--lh-normal)' }}>
          Configure workspace, accent, peers, etc. after.
        </div>
      </div>

      {noProviders ? (
        <div className="col" style={{ gap: 10 }}>
          <FLabel>Provider · pick one to start</FLabel>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            {PROVIDER_TYPES.map(p => (
              <button
                key={p}
                className={'pill ' + (p === provKind ? 'is-on' : 'is-off')}
                onClick={() => setProvKind(p)}
              >● {p}</button>
            ))}
          </div>
          <div className="row" style={{ gap: 10, alignItems: 'flex-end' }}>
            <div className="col" style={{ flex: 1, gap: 6 }}>
              <FLabel>Name</FLabel>
              <input
                className="field"
                value={provName}
                onChange={e => setProvName(e.target.value)}
                placeholder="local · home-gpu · cloud-a"
              />
            </div>
            <div className="col" style={{ flex: 1.4, gap: 6 }}>
              <FLabel>{urlLabel}</FLabel>
              <input
                className={provKind === 'Ollama' ? 'field' : 'field field-mono'}
                value={provUrl}
                onChange={e => setProvUrl(e.target.value)}
                placeholder={urlPlaceholder}
              />
            </div>
          </div>
        </div>
      ) : (
        <div>
          <FLabel>Model</FLabel>
          <div className="row" style={{ gap: 8, alignItems: 'center' }}>
            <window.ModelPicker currentModel={model} accent={accent} onChange={setModel} />
            <button className="alink" onClick={() => onOpenProviders?.()}>Providers</button>
          </div>
        </div>
      )}

      <div className="row" style={{ justifyContent: 'flex-end', gap: 12 }}>
        <button className="alink" onClick={onClose}>Cancel</button>
        <button
          className="btn btn-primary"
          disabled={!valid}
          style={{ opacity: valid ? 1 : 0.4 }}
          onClick={() => {
            const out = { id: slug, color: accent, model };
            if (noProviders) out.provider = { kind: provKind, name: provName.trim(), url: provUrl.trim() };
            onCreate?.(out);
            onClose();
          }}
        >Create</button>
      </div>
    </Modal>
  );
}

// ── New workgroup · minimal create modal ──────────────────────────────
function NewWorkgroupModal({ open, onClose, onCreate }) {
  const [hub, setHub] = useStateP('alpi');
  const [name, setName] = useStateP('');
  const [members, setMembers] = useStateP(new Set());
  const [briefing, setBriefing] = useStateP('');

  useEffectP(() => {
    if (open) { setHub('alpi'); setName(''); setMembers(new Set()); setBriefing(''); }
  }, [open]);

  if (!open) return null;

  const PROFILES = window.MOCK.PROFILES;
  const hubProfile = PROFILES.find(p => p.id === hub);
  // Candidates: peers of the hub (other profiles); exclude the hub itself.
  const candidates = PROFILES.filter(p => p.id !== hub).slice(0, 12);
  const valid = name.trim().length >= 2;
  const slug = name.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-');

  const toggle = (id) => {
    setMembers(s => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  return (
    <Modal open={open} onClose={onClose} title={null} width={520}>
      <strong style={{ fontSize: 15 }}>New workgroup</strong>

      <div>
        <FLabel>Hub</FLabel>
        <select
          value={hub}
          onChange={e => { setHub(e.target.value); setMembers(new Set()); }}
          className="field field-mono"
          style={{ fontSize: 13 }}
        >
          {PROFILES.map(p => <option key={p.id} value={p.id}>@{p.id}</option>)}
        </select>
      </div>

      <div>
        <FLabel>Name</FLabel>
        <input
          autoFocus
          value={name}
          onChange={e => setName(e.target.value)}
          className="field"
          placeholder="team-alpha · roadmap · customers"
        />
      </div>

      <div>
        <FLabel>Members — peers of @{hub}</FLabel>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
          {candidates.map(c => {
            const sel = members.has(c.id);
            return (
              <button
                key={c.id}
                onClick={() => toggle(c.id)}
                className={'pill ' + (sel ? 'is-on' : '')}
                style={{ cursor: 'pointer', opacity: sel ? 1 : .8 }}
              >
                <span className="diamond" style={{ '--c': c.color, width: 7, height: 7 }} />
                <span>@{c.id}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <FLabel>Briefing (optional)</FLabel>
        <textarea
          value={briefing}
          onChange={e => setBriefing(e.target.value)}
          className="field"
          rows={3}
          placeholder="what is this workgroup about? who does what?"
          style={{ minHeight: 72, lineHeight: 'var(--lh-normal)' }}
        />
      </div>

      <div className="row" style={{ justifyContent: 'flex-end', gap: 12 }}>
        <button className="alink" onClick={onClose}>Cancel</button>
        <button
          className="btn btn-primary"
          disabled={!valid}
          style={{ opacity: valid ? 1 : 0.4 }}
          onClick={() => { onCreate?.({ id: slug, hub, members: [hub, ...members], briefing }); onClose(); }}
        >Create</button>
      </div>
    </Modal>
  );
}

Object.assign(window, { NewProfileModal, NewWorkgroupModal });

