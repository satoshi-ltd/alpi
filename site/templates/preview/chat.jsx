// chat.jsx — chat header, message stream, composer, new-chat empty state.

const { useState: useStateChat, useEffect: useEffectChat, useRef: useRefChat, useMemo: useMemoChat } = React;

// Cost meter — sleek bar with caret marker for budget consumed.
function BudgetMeter({ used, cap, accent, compact }) {
  const pct = Math.max(0, Math.min(1, used / cap));
  return (
    <div className="row row-gap" style={{ gap: 8 }}>
      <span className="mono" style={{ color: 'var(--ink-2)', fontSize: 12 }}>
        ${used.toFixed(2)}<span style={{ color: 'var(--ink-3)' }}>/${cap.toFixed(2)}</span>
      </span>
      {!compact &&
      <span style={{
        width: 76, height: 4, borderRadius: 999,
        background: 'var(--line)', position: 'relative', overflow: 'hidden'
      }}>
          <span style={{
          position: 'absolute', inset: 0,
          width: `${pct * 100}%`,
          background: accent,
          borderRadius: 999
        }} />
        </span>
      }
    </div>);

}

// Compact meter chip: `label [mini-bar] pct` — used inline in chat header.
function MeterChip({ label, value, pct, color, tip, tipSide = 'down' }) {
  const p = Math.max(0, Math.min(1, pct));
  const chip = (
    <span className="row row-gap" style={{ gap: 8 }}>
      <span className="mono tnum" style={{ fontSize: 11, color: 'var(--ink-2)' }}>{value}</span>
      <span style={{
        width: 56, height: 5, borderRadius: 999,
        background: 'var(--line)', position: 'relative', overflow: 'hidden',
      }}>
        <span style={{
          position: 'absolute', inset: 0,
          width: `${p * 100}%`,
          background: color,
          borderRadius: 999,
        }} />
      </span>
      <span className="mono tnum" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{Math.round(p * 100)}%</span>
    </span>
  );
  if (!tip) return chip;
  return <window.Tip text={tip} side={tipSide}>{chip}</window.Tip>;
}

function formatTokens(n) {
  if (n >= 1000) return `${(n/1000).toFixed(n >= 10000 ? 0 : 1)}K`;
  return String(n);
}

// Model picker — composer dropdown grouped by provider.
function ModelPicker({ currentModel, accent }) {
  const [open, setOpen] = useStateChat(false);
  const [picked, setPicked] = useStateChat(currentModel);
  const ref = useRefChat(null);
  const MODELS = window.MOCK.MODELS;

  useEffectChat(() => {
    if (!open) return;
    const onDoc = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  // Re-sync when the profile changes
  useEffectChat(() => { setPicked(currentModel); }, [currentModel]);

  const label = picked.split('/')[1] || picked;

  return (
    <span ref={ref} style={{ position: 'relative' }}>
      <window.Tip text="Model — overrides for this message" side="up">
        <button
          className="btn btn-ghost"
          onClick={() => setOpen(o => !o)}
          style={{ height: 26 }}
        >
          <window.I.Spark style={{ width: 12, height: 12, color: 'var(--ink-3)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{label}</span>
          <window.I.ChevDown style={{ width: 12, height: 12 }} />
        </button>
      </window.Tip>
      {open && (
        <div className="anim-pop" style={{
          position: 'absolute', bottom: 'calc(100% + 8px)', right: 0,
          width: 340, background: 'var(--bg-elev)',
          border: '.5px solid var(--line-2)', borderRadius: 12,
          boxShadow: 'var(--shadow)', zIndex: 50,
          overflow: 'hidden',
        }}>
          <div className="col" style={{ padding: 6, maxHeight: 420, overflowY: 'auto' }}>
            {Object.entries(MODELS).map(([provider, models]) => (
              <div key={provider}>
                <div className="eyebrow" style={{ padding: '10px 10px 4px' }}>{provider}</div>
                {models.map(m => {
                  const sel = picked === m.id;
                  return (
                    <button
                      key={m.id}
                      onClick={() => { setPicked(m.id); setOpen(false); }}
                      className="row"
                      style={{
                        padding: '8px 10px', borderRadius: 8, gap: 10,
                        textAlign: 'left',
                        background: sel ? 'var(--selected)' : 'transparent',
                        alignItems: 'center', width: '100%',
                      }}
                      onMouseEnter={e => { if (!sel) e.currentTarget.style.background = 'var(--hover)'; }}
                      onMouseLeave={e => { if (!sel) e.currentTarget.style.background = 'transparent'; }}
                    >
                      <span style={{
                        width: 14, display: 'inline-flex', justifyContent: 'center',
                        color: sel ? accent : 'transparent',
                      }}>
                        {sel && <window.I.Check style={{ width: 13, height: 13, strokeWidth: 2.4 }} />}
                      </span>
                      <span className="col" style={{ flex: 1, gap: 1 }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: sel ? 600 : 400 }}>{m.label}</span>
                        <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{formatTokens(m.ctx)} ctx</span>
                      </span>
                      {m.badge && (
                        <span className="tag" style={{ fontSize: 11 }}>{m.badge}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
          <div className="row between" style={{
            padding: '8px 12px', borderTop: '.5px solid var(--line)',
            background: 'var(--bg-side)', fontSize: 11, color: 'var(--ink-3)',
          }}>
            <span>Override for this message only</span>
            <button style={{ fontSize: 11, color: 'var(--ink-2)' }}
              onMouseEnter={e => e.currentTarget.style.textDecoration = 'underline'}
              onMouseLeave={e => e.currentTarget.style.textDecoration = 'none'}
            >Set default…</button>
          </div>
        </div>
      )}
    </span>
  );
}

// Markdown-lite — paragraphs, bold, inline `code`, multi-line ```code blocks```.
function renderRich(text) {
  const blocks = [];
  const lines = text.split('\n');
  let i = 0;
  let para = [];
  const flushPara = () => {
    if (para.length === 0) return;
    blocks.push(<RichParagraph key={blocks.length} text={para.join('\n')} />);
    para = [];
  };
  while (i < lines.length) {
    const l = lines[i];
    // fenced code block
    if (l.trim().startsWith('```')) {
      flushPara();
      i++;
      const code = [];
      while (i < lines.length && !lines[i].trim().startsWith('```')) { code.push(lines[i]); i++; }
      if (i < lines.length) i++; // skip closing ```
      blocks.push(
        <pre key={blocks.length} style={{
          margin: '12px 0', padding: '12px 14px',
          background: 'color-mix(in srgb, var(--ink) 4%, var(--bg-pane))',
          border: '.5px solid var(--line)', borderRadius: 8,
          fontFamily: 'var(--font-mono)', fontSize: 12,
          overflowX: 'auto', whiteSpace: 'pre', lineHeight: 'var(--lh-normal)',
        }}><code>{code.join('\n')}</code></pre>
      );
      continue;
    }
    // markdown heading
    if (l.startsWith('## ')) {
      flushPara();
      blocks.push(<h3 key={blocks.length} style={{ margin: '20px 0 8px', fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em' }}>{l.slice(3)}</h3>);
      i++; continue;
    }
    // blank line breaks paragraphs
    if (l.trim() === '') {
      flushPara();
      i++; continue;
    }
    para.push(l);
    i++;
  }
  flushPara();
  return blocks;
}

function RichParagraph({ text }) {
  // Handle bullet lists (lines starting with -, *, or •) within a paragraph
  const lines = text.split('\n');
  const isBulletList = lines.length > 1 && lines.every(l => /^[\-*•]\s+/.test(l.trim()));
  if (isBulletList) {
    return (
      <ul style={{ margin: '8px 0', paddingLeft: 22, lineHeight: 1.6 }}>
        {lines.map((l, i) => (
          <li key={i} style={{ marginBottom: 3 }}>{inlineMd(l.replace(/^[\-*•]\s+/, ''))}</li>
        ))}
      </ul>
    );
  }
  return (
    <p style={{ margin: '8px 0', textWrap: 'pretty' }}>
      {lines.map((l, i) => (
        <React.Fragment key={i}>
          {inlineMd(l)}
          {i < lines.length - 1 && <br />}
        </React.Fragment>
      ))}
    </p>
  );
}

function inlineMd(s) {
  return s.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((seg, i) => {
    if (seg.startsWith('**') && seg.endsWith('**')) {
      return <strong key={i} style={{ fontWeight: 600 }}>{seg.slice(2, -2)}</strong>;
    }
    if (seg.startsWith('`') && seg.endsWith('`')) {
      return <code key={i} style={{ fontFamily: 'var(--font-mono)', fontSize: '.92em', background: 'var(--hover)', padding: '1px 5px', borderRadius: 4 }}>{seg.slice(1, -1)}</code>;
    }
    return <React.Fragment key={i}>{seg}</React.Fragment>;
  });
}

// One agent reply / user message bubble.
function Message({ m, profile, isUser, isHub, hubColor, subject, accent, onJumpToTask }) {
  // ── Marker messages: TASK / WORKING / SKIP / DONE — distinct cards instead of bubbles ──
  if (['task', 'working', 'skip', 'done'].includes(m.marker)) {
    return <TaskMarker m={m} profile={profile} hubColor={hubColor} subject={subject} />;
  }

  // ── Profile (1:1) chat — ChatGPT/Claude style ──
  // user → right, in a tinted bubble with max width
  // agent → full-width, no bubble, no name; floating actions on hover
  if (subject?.kind === 'profile') {
    return <ProfileMessage m={m} profile={profile} isUser={isUser} accent={accent} />;
  }

  // ── Workgroup chat — agent-to-agent only. User does NOT participate. ──
  // Hub → right with bubble + name
  // Members → left with bubble + name
  if (isUser) return null;

  const alignRight = isHub;
  const align = alignRight ? 'flex-end' : 'flex-start';
  const bubbleTint = profile
    ? `color-mix(in srgb, ${profile.color} 11%, var(--bg-pane))`
    : 'var(--hover)';

  const metaItems = [];
  if (m.tokens != null) metaItems.push(<span key="tk" className="mono" style={{ color: 'var(--ink-4)', fontSize: 11 }}>{(m.tokens / 1000).toFixed(1)}K</span>);
  if (m.cost != null)   metaItems.push(<span key="$" className="mono" style={{ color: 'var(--ink-4)', fontSize: 11 }}>${m.cost.toFixed(4)}</span>);
  if (m.seq != null)    metaItems.push(<span key="seq" className="mono" style={{ color: 'var(--ink-3)', fontSize: 11 }}>#{m.seq}</span>);
  const nameNode = profile ? (
    <span key="who" className="row row-gap" style={{ gap: 5 }}>
      {alignRight ? null : <span className="diamond" style={{ '--c': profile.color, width: 8, height: 8 }} />}
      <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--ink-2)' }}>{profile.id}</span>
      {alignRight ? <span className="diamond" style={{ '--c': profile.color, width: 8, height: 8 }} /> : null}
    </span>
  ) : null;

  const meta = alignRight ? [...metaItems, nameNode] : [nameNode, ...metaItems];

  // optional in-task tag (linkable to its parent #task) — removed: tasks are sequential, not multithread
  const taskTag = null;

  return (
    <div
      data-msg-task={m.taskId || ''}
      style={{
        display: 'flex', flexDirection: 'column',
        alignItems: align, gap: 6, width: '100%',
      }}
    >
      <div className="row row-gap" style={{ fontSize: 11, color: 'var(--ink-3)', flexDirection: alignRight ? 'row-reverse' : 'row', alignItems: 'baseline', gap: 10 }}>
        {meta.map((n, i) => n ? React.cloneElement(n, { key: i }) : null)}
      </div>
      <div style={{
        maxWidth: 'var(--bubble-max)',
        padding: '13px 17px',
        borderRadius: 14,
        background: bubbleTint,
        color: 'var(--ink)',
        boxShadow: 'var(--shadow-sm)',
        lineHeight: 'var(--lh-normal)',
        fontSize: 14,
        textWrap: 'pretty',
      }}>
        {renderRich(m.text)}
      </div>
      {taskTag}
    </div>
  );
}

// Tool call row — sits above an agent's response text. Shows tool name + args dim mono.
// Status per call: 'success' (default, accent color) · 'error' (red) · 'running' (pulsing accent).
function ToolCallRow({ call, profileColor }) {
  const status = call.status || 'success';
  const isRunning = status === 'running';
  const dotColor =
    status === 'error'   ? 'var(--c-danger)' :
    profileColor || 'var(--ink-3)';
  return (
    <div className="row row-gap" style={{
      gap: 10, padding: '6px 12px',
      borderRadius: 8,
      background: isRunning
        ? `color-mix(in srgb, ${profileColor || 'var(--ink)'} 6%, var(--bg-pane))`
        : 'color-mix(in srgb, var(--ink) 3%, var(--bg-pane))',
      border: '.5px solid ' + (isRunning ? `color-mix(in srgb, ${profileColor || 'var(--ink)'} 30%, transparent)` : 'var(--line)'),
      fontFamily: 'var(--font-mono)', fontSize: 12,
      width: 'fit-content', maxWidth: '100%',
    }}>
      <span
        className="diamond"
        style={{
          '--c': dotColor,
          width: 8, height: 8,
          animation: isRunning ? 'pulse-dot 1.4s ease-in-out infinite' : 'none',
        }}
      />
      <span style={{ color: 'var(--ink)', fontWeight: 500 }}>{call.name}</span>
      <span style={{
        color: 'var(--ink-3)',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        minWidth: 0,
      }}>
        {renderToolArgs(call.args)}
      </span>
      {isRunning && (
        <span style={{ display: 'inline-flex', gap: 2, alignItems: 'center', marginLeft: 2, color: profileColor || 'var(--ink-3)' }}>
          {[0,1,2].map(i => (
            <span key={i} style={{
              width: 3, height: 3, borderRadius: '50%',
              background: 'currentColor',
              animation: `pulse-dot 1.4s ease-in-out ${i*0.2}s infinite`,
            }} />
          ))}
        </span>
      )}
    </div>
  );
}

// Parse a flat "key=val key=val" args string and render keys in --ink-4, values in --ink-2.
function renderToolArgs(s) {
  if (!s) return null;
  const parts = String(s).split(/(\s+)/);
  return parts.map((p, i) => {
    if (/^\s+$/.test(p)) return <React.Fragment key={i}>{p}</React.Fragment>;
    const eq = p.indexOf('=');
    if (eq === -1) return <span key={i} style={{ color: 'var(--ink-3)' }}>{p}</span>;
    return (
      <React.Fragment key={i}>
        <span style={{ color: 'var(--ink-4)' }}>{p.slice(0, eq + 1)}</span>
        <span style={{ color: 'var(--ink-2)' }}>{p.slice(eq + 1)}</span>
      </React.Fragment>
    );
  });
}

// ── 1:1 profile message — ChatGPT/Claude style ─────────────────────────
function ProfileMessage({ m, profile, isUser, accent }) {
  // mock timestamp — relative to "now"
  const ts = m.ts || (m.id ? relativeTs(m.id) : 'now');
  const [copied, setCopied] = useStateChat(false);
  const onCopy = () => {
    navigator.clipboard?.writeText(m.text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  if (isUser) {
    return (
      <div className="msg-row" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, width: '100%' }}>
        <div style={{
          maxWidth: 'var(--bubble-max)',
          padding: '12px 16px',
          borderRadius: 14,
          background: `color-mix(in srgb, ${accent} 12%, var(--bg-pane))`,
          color: 'var(--ink)',
          fontSize: 14,
          lineHeight: 'var(--lh-normal)',
          textWrap: 'pretty',
          boxShadow: 'var(--shadow-sm)',
        }}>
          {renderRich(m.text)}
        </div>
        <div style={{
          display: 'flex', gap: 2, alignItems: 'center',
          color: 'var(--ink-3)', fontSize: 11,
          marginTop: 2,
        }}>
          <span className="mono" style={{ marginRight: 6 }}>{ts}</span>
          <window.Tip text="Retry from here" side="up">
            <button className="iconbtn" style={{ width: 24, height: 24 }}>
              <window.I.Refresh style={{ width: 12, height: 12 }} />
            </button>
          </window.Tip>
          <window.Tip text="Edit message" side="up">
            <button className="iconbtn" style={{ width: 24, height: 24 }}>
              <svg viewBox="0 0 16 16" className="icon" style={{ width: 12, height: 12 }}>
                <path d="M11 2.5l2.5 2.5L6 12.5H3.5V10z"/>
              </svg>
            </button>
          </window.Tip>
          <window.Tip text={copied ? 'Copied' : 'Copy'} side="up">
            <button className="iconbtn" style={{ width: 24, height: 24 }} onClick={onCopy}>
              {copied
                ? <window.I.Check style={{ width: 12, height: 12, strokeWidth: 2.2, color: 'var(--c-success)' }} />
                : <window.I.Copy style={{ width: 12, height: 12 }} />
              }
            </button>
          </window.Tip>
        </div>
      </div>
    );
  }

  // Agent — full-width, no bubble, no name. Tool calls (if any) precede the text.
  return (
    <div className="msg-row" style={{ display: 'flex', flexDirection: 'column', alignItems: 'stretch', gap: 10, width: '100%' }}>
      {m.tool_calls && m.tool_calls.length > 0 && (
        <div className="col" style={{ gap: 4 }}>
          {m.tool_calls.map((c, i) => <ToolCallRow key={i} call={c} profileColor={profile?.color} />)}
        </div>
      )}
      {m.thinking ? (
        <div style={{ padding: '8px 0', color: 'var(--ink-3)' }}>
          <window.Activity size="xl" />
        </div>
      ) : (
        <>
          <div style={{
            color: 'var(--ink)',
            fontSize: 15, lineHeight: 'var(--lh-relaxed)',
            textWrap: 'pretty',
            letterSpacing: '-0.003em',
          }}>
            {renderRich(m.text)}
          </div>
          <div className="msg-actions" style={{
            opacity: 0, transition: 'opacity .15s var(--ease)',
            display: 'flex', gap: 2, alignItems: 'center', marginTop: 4,
            color: 'var(--ink-3)', fontSize: 11,
          }} data-search-skip="1">
            <window.Tip text={copied ? 'Copied' : 'Copy response'} side="up">
              <button className="iconbtn" style={{ width: 26, height: 26 }} onClick={onCopy}>
                {copied
                  ? <window.I.Check style={{ width: 13, height: 13, strokeWidth: 2.2, color: 'var(--c-success)' }} />
                  : <window.I.Copy style={{ width: 13, height: 13 }} />
                }
              </button>
            </window.Tip>
            <window.Tip text="Retry from here" side="up">
              <button className="iconbtn" style={{ width: 26, height: 26 }}>
                <window.I.Refresh style={{ width: 13, height: 13 }} />
              </button>
            </window.Tip>
            <window.Tip text="Read aloud" side="up">
              <button className="iconbtn" style={{ width: 26, height: 26 }}>
                <svg viewBox="0 0 16 16" className="icon" style={{ width: 13, height: 13 }}>
                  <path d="M3 6v4h2l3 2.5V3.5L5 6H3z"/>
                  <path d="M10.5 5.5a3 3 0 010 5M12.5 3.5a5.5 5.5 0 010 9"/>
                </svg>
              </button>
            </window.Tip>
            <span style={{ marginLeft: 8 }}>
              <span className="mono">{ts}</span>
              {m.tokens != null && <>
                <span style={{ margin: '0 6px', color: 'var(--ink-4)' }}>·</span>
                <span className="mono">{(m.tokens / 1000).toFixed(1)}K</span>
              </>}
              {m.cost != null && <>
                <span style={{ margin: '0 6px', color: 'var(--ink-4)' }}>·</span>
                <span className="mono">${m.cost.toFixed(4)}</span>
              </>}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

// Very simple relative-time formatter for mock messages.
function relativeTs(id) {
  // mock ids are sequential ints — fake a "now / 2m ago / …" cadence
  const n = id % 6;
  return ['now', '1m', '3m', '5m', '12m', '1h'][n];
}

// TASK / WORKING / SKIP / DONE — visually distinct cards (anchorable, scannable in long threads)
function TaskMarker({ m, profile, hubColor, subject }) {
  const kind = m.marker; // 'task' | 'working' | 'skip' | 'done'
  const color = hubColor || profile?.color || 'var(--ink-2)';

  // Per-marker visual config
  const config = {
    task:    { label: 'TASK',    tintPct: 11, eyebrowMix: 'var(--ink-3)',                              tintBaseColor: color, icon: <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'currentColor', display: 'inline-block' }} /> },
    working: { label: 'WORKING', tintPct: 14, eyebrowMix: `color-mix(in srgb, ${color} 70%, var(--ink))`, tintBaseColor: color, icon: <WorkingDots /> },
    skip:    { label: 'SKIP',    tintPct: 12, eyebrowMix: '#a98113',                                   tintBaseColor: 'var(--c-warning)', icon: <SkipIcon /> },
    done:    { label: 'DONE',    tintPct: 18, eyebrowMix: `color-mix(in srgb, ${color} 75%, var(--ink))`, tintBaseColor: color, icon: <window.I.Check style={{ width: 11, height: 11, strokeWidth: 2.2 }} /> },
  }[kind] || { label: kind?.toUpperCase() || 'TASK', tintPct: 11, eyebrowMix: 'var(--ink-3)', tintBaseColor: color, icon: null };

  return (
    <div
      id={`task-${m.taskId}`}
      data-task-marker={kind}
      data-msg-task={m.taskId || ''}
      style={{
        display: 'flex', flexDirection: 'column',
        alignItems: 'flex-end', gap: 6, width: '100%',
        scrollMarginTop: 120,
      }}
    >
      {/* meta line — same shape as regular hub message */}
      <div className="row row-gap" style={{ fontSize: 11, color: 'var(--ink-3)', flexDirection: 'row-reverse' }}>
        <span className="row row-gap" style={{ gap: 5 }}>
          <span style={{ fontWeight: 600, color: 'var(--ink-2)' }}>{profile?.id}</span>
          <span className="diamond" style={{ '--c': color, width: 7, height: 7 }} />
        </span>
        {m.seq != null && <span className="mono" style={{ color: 'var(--ink-3)' }}>#{m.seq}</span>}
        {m.cost != null && <span className="mono" style={{ color: 'var(--ink-4)' }}>${m.cost.toFixed(4)}</span>}
        {m.tokens != null && <span className="mono" style={{ color: 'var(--ink-4)' }}>{(m.tokens/1000).toFixed(1)}K</span>}
      </div>

      <div style={{
        maxWidth: 'var(--bubble-max)',
        padding: '14px 18px 16px',
        borderRadius: 14,
        background: `color-mix(in srgb, ${config.tintBaseColor} ${config.tintPct}%, var(--bg-pane))`,
        boxShadow: 'var(--shadow-sm)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* eyebrow: TASK / WORKING / SKIP / DONE */}
        <div className="row row-gap" style={{
          fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, letterSpacing: '.10em',
          color: config.eyebrowMix,
          marginBottom: 6, gap: 8,
        }}>
          <span className="row row-gap" style={{ gap: 5 }}>
            {config.icon}
            <span>{config.label}</span>
          </span>
        </div>
        {/* Task title — visually prominent */}
        {m.taskTitle && (
          <div style={{
            fontFamily: 'var(--font-sans)', fontSize: 15, fontWeight: 600,
            color: 'var(--ink)', lineHeight: 'var(--lh-cozy)', marginBottom: 8,
            letterSpacing: '-0.01em',
          }}>{m.taskTitle}</div>
        )}
        <div style={{ fontSize: 14, lineHeight: 'var(--lh-normal)', color: 'var(--ink)', textWrap: 'pretty' }}>
          {renderRich(m.text)}
        </div>
      </div>
    </div>
  );
}

// 3-dot loader for working state
function WorkingDots() {
  return (
    <span style={{ display: 'inline-flex', gap: 2, alignItems: 'center' }}>
      {[0,1,2].map(i => (
        <span key={i} style={{
          width: 4, height: 4, borderRadius: '50%',
          background: 'currentColor',
          animation: `pulse-dot 1.4s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
    </span>
  );
}

function SkipIcon() {
  return (
    <svg viewBox="0 0 16 16" style={{ width: 11, height: 11, stroke: 'currentColor', fill: 'none', strokeWidth: 2 }}>
      <circle cx="8" cy="8" r="6" />
      <path d="M4 12L12 4" />
    </svg>
  );
}

// Task index popover — opens from a button in the chat header.
function TasksButton({ thread, hubColor, onJump }) {
  const [open, setOpen] = useStateChat(false);
  const ref = useRefChat(null);

  useEffectChat(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const tasks = useMemoChat(() => {
    const m = new Map();
    thread.forEach(msg => {
      if (msg.taskId && !m.has(msg.taskId)) {
        m.set(msg.taskId, { id: msg.taskId, title: msg.taskTitle, status: msg.marker || null, contributions: 0 });
      }
      if (msg.taskId) m.get(msg.taskId).contributions++;
      // Status reflects the LATEST marker — task → working → done|skip
      if (msg.taskId && ['working', 'done', 'skip'].includes(msg.marker)) {
        m.get(msg.taskId).status = msg.marker;
      }
    });
    return [...m.values()];
  }, [thread]);

  if (tasks.length === 0) return null;
  const closed = tasks.filter(t => t.status === 'done' || t.status === 'skip').length;
  const active = tasks.find(t => !['done', 'skip'].includes(t.status));
  const activeLabel = active ? (active.title || active.id) : null;
  const truncated = activeLabel && activeLabel.length > 32
    ? activeLabel.slice(0, 32).trim() + '…'
    : activeLabel;

  return (
    <span ref={ref} style={{ position: 'relative' }}>
      <window.Tip text={active ? "Active #task · click for history" : "All tasks resolved · click for history"} side="r">
        <button
          className="btn btn-ghost"
          onClick={() => setOpen(o => !o)}
          style={{ height: 28, maxWidth: 360 }}
        >
          {active ? (
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: hubColor, flexShrink: 0,
              boxShadow: `0 0 0 2px color-mix(in srgb, ${hubColor} 25%, transparent)`,
            }} />
          ) : (
            <window.I.Check style={{ width: 13, height: 13, strokeWidth: 2.2, color: hubColor }} />
          )}
          <span style={{
            fontSize: 12, color: 'var(--ink)', fontWeight: 500,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
            maxWidth: 220,
          }}>
            {active ? truncated : 'All tasks resolved'}
          </span>
          <span className="tnum mono" style={{ fontSize: 11, color: 'var(--ink-3)', flexShrink: 0 }}>
            {closed}/{tasks.length}
          </span>
          <window.I.ChevDown style={{ width: 12, height: 12, flexShrink: 0 }} />
        </button>
      </window.Tip>
      {open && (
        <div className="anim-pop" style={{
          position: 'absolute', top: 'calc(100% + 8px)', right: 0,
          width: 380, background: 'var(--bg-elev)',
          border: '.5px solid var(--line-2)', borderRadius: 12,
          boxShadow: 'var(--shadow)', zIndex: 50,
          overflow: 'hidden',
        }}>
          <div style={{ padding: '10px 14px', borderBottom: '.5px solid var(--line)', background: 'var(--bg-side)' }}>
            <div className="row row-gap" style={{ gap: 8 }}>
              <span className="eyebrow">{active ? 'Active task' : 'Task history'}</span>
              <span className="tag tnum">{closed}/{tasks.length}</span>
            </div>
            <p style={{ margin: '6px 0 0', fontSize: 11, color: 'var(--ink-3)', lineHeight: 'var(--lh-normal)' }}>
              {active
                ? <>The hub opens one <code className="mono" style={{ fontSize: 11, color: 'var(--ink-2)' }}>#task</code> at a time and closes it with <code className="mono" style={{ fontSize: 11, color: 'var(--ink-2)' }}>#done</code>.</>
                : <>Open a new task — <code className="mono" style={{ fontSize: 11, color: 'var(--ink-2)' }}>#task &lt;question&gt;</code> from the hub.</>
              }
            </p>
          </div>
          <div className="col" style={{ padding: 6, maxHeight: 320, overflowY: 'auto' }}>
            {tasks.map(t => {
              const isDone = t.status === 'done';
              const isSkip = t.status === 'skip';
              const isWorking = t.status === 'working';
              const isOpen = !isDone && !isSkip;
              return (
                <button
                  key={t.id}
                  onClick={() => { onJump(t.id); setOpen(false); }}
                  className="row"
                  style={{
                    padding: '10px 12px', borderRadius: 8, gap: 10,
                    textAlign: 'left', alignItems: 'flex-start',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--hover)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <span style={{
                    paddingTop: 2, flexShrink: 0,
                    color: isDone ? hubColor :
                           isSkip ? 'var(--c-warning)' :
                           isWorking ? hubColor : 'var(--ink-3)'
                  }}>
                    {isDone
                      ? <window.I.Check style={{ width: 14, height: 14, strokeWidth: 2.2 }} />
                      : isSkip
                        ? <svg viewBox="0 0 16 16" style={{ width: 13, height: 13, stroke: 'currentColor', fill: 'none', strokeWidth: 2 }}><circle cx="8" cy="8" r="6"/><path d="M4 12L12 4"/></svg>
                        : isWorking
                          ? <span style={{ display: 'inline-flex', gap: 2, alignItems: 'center', paddingTop: 4 }}>
                              {[0,1,2].map(i => (
                                <span key={i} style={{ width: 4, height: 4, borderRadius: '50%', background: 'currentColor', animation: `pulse-dot 1.4s ease-in-out ${i*0.2}s infinite` }} />
                              ))}
                            </span>
                          : <span style={{ width: 9, height: 9, borderRadius: '50%', border: '1.5px solid currentColor', display: 'inline-block', marginTop: 1 }} />
                    }
                  </span>
                  <div className="col" style={{ flex: 1, minWidth: 0, gap: 3 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)', lineHeight: 'var(--lh-cozy)', textWrap: 'pretty' }}>{t.title || t.id}</div>
                    <div className="row row-gap" style={{ gap: 8, fontSize: 11, color: 'var(--ink-3)' }}>
                      <span className="mono">#{t.id}</span>
                      <span style={{ color: 'var(--ink-4)' }}>·</span>
                      <span className="mono tnum">{t.contributions} msg{t.contributions !== 1 ? 's' : ''}</span>
                      <span style={{ color: 'var(--ink-4)' }}>·</span>
                      <span style={{
                        color: isDone ? `color-mix(in srgb, ${hubColor} 70%, var(--ink-3))` :
                               isSkip ? '#a98113' :
                               isWorking ? `color-mix(in srgb, ${hubColor} 70%, var(--ink-3))` :
                                            'var(--ink-3)',
                      }}>
                        {isDone ? 'done' : isSkip ? 'skipped' : isWorking ? 'working' : 'open'}
                      </span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </span>
  );
}

// Sessions popover for profile chats — list previous threads + new session button.
function SessionsButton({ profileId, onNew, onPick }) {
  const [open, setOpen] = useStateChat(false);
  const ref = useRefChat(null);
  useEffectChat(() => {
    if (!open) return;
    const onDoc = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  // Mock sessions per profile — first message preview + turn count, grouped by day.
  const SESSIONS = useMemoChat(() => {
    const byProfile = {
      doc: [
        { id: 1, day: 'today',     preview: '@peer como ves las vitaminas que to…', turns: 8,  current: true },
        { id: 2, day: 'today',     preview: 'vale, ves que dispostivios tengo en c…', turns: 10 },
        { id: 3, day: 'today',     preview: 'que dispositivos ves en mi casa?',       turns: 12 },
        { id: 4, day: 'today',     preview: 'que dispositivos puedes ver en mi alp…', turns: 4 },
        { id: 5, day: 'yesterday', preview: 'ask @pantry for dinner ideas',           turns: 13 },
        { id: 6, day: 'yesterday', preview: 'vale revisa el unico schedule que tene…', turns: 7 },
      ],
      builder: [
        { id: 1, day: 'today',     preview: 'Refactor this PR for clarity',           turns: 18, current: true },
        { id: 2, day: 'yesterday', preview: 'Why is the test suite 22 minutes?',      turns: 24 },
        { id: 3, day: 'last week', preview: 'Audit deps for stale/insecure',          turns: 9 },
      ],
    };
    return byProfile[profileId] || [
      { id: 1, day: 'today', preview: 'New thread', turns: 0, current: true },
    ];
  }, [profileId]);

  const grouped = useMemoChat(() => {
    const g = new Map();
    SESSIONS.forEach(s => {
      if (!g.has(s.day)) g.set(s.day, []);
      g.get(s.day).push(s);
    });
    return [...g.entries()];
  }, [SESSIONS]);

  return (
    <span ref={ref} className="row row-gap" style={{ position: 'relative', gap: 0 }}>
      <window.Tip text="Sessions — switch or browse history" side="r">
        <button
          className="btn btn-ghost"
          onClick={() => setOpen(o => !o)}
          style={{ height: 28 }}
        >
          <span>Sessions</span>
          <window.I.ChevDown style={{ width: 12, height: 12 }} />
        </button>
      </window.Tip>
      <window.Tip text="New session" side="r">
        <button
          className="iconbtn"
          onClick={onNew}
        >
          <window.I.Plus />
        </button>
      </window.Tip>
      {open && (
        <div className="anim-pop" style={{
          position: 'absolute', top: 'calc(100% + 8px)', right: 0,
          width: 400, background: 'var(--bg-elev)',
          border: '.5px solid var(--line-2)', borderRadius: 12,
          boxShadow: 'var(--shadow)', zIndex: 50, overflow: 'hidden',
        }}>
          <div className="col" style={{ padding: 6, maxHeight: 420, overflowY: 'auto' }}>
            {grouped.map(([day, items]) => (
              <div key={day}>
                <div className="eyebrow" style={{ padding: '10px 12px 4px' }}>{day}</div>
                {items.map(s => (
                  <button
                    key={s.id}
                    onClick={() => { onPick?.(s); setOpen(false); }}
                    className="row"
                    style={{
                      width: '100%', padding: '8px 12px', borderRadius: 8, gap: 10,
                      background: s.current ? 'var(--selected)' : 'transparent',
                      textAlign: 'left',
                    }}
                    onMouseEnter={e => { if (!s.current) e.currentTarget.style.background = 'var(--hover)'; }}
                    onMouseLeave={e => { if (!s.current) e.currentTarget.style.background = 'transparent'; }}
                  >
                    <span style={{
                      flex: 1, fontSize: 13,
                      color: 'var(--ink)',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>{s.preview}</span>
                    <span className="tag" style={{ flexShrink: 0 }}>{s.turns} turns</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </span>
  );
}

// Banner — strip across the top of the chat main pane. Kinds: 'info' | 'warning' | 'danger'
function Banner({ kind = 'info', dot, children, action }) {
  return (
    <div className={'banner is-' + kind}>
      <span className="b-dot pulse-dot" style={{ background: dot || ({
        info: 'var(--ink-3)', warning: 'var(--c-warning)', danger: 'var(--c-danger)'
      })[kind] }} />
      <span style={{ flex: 1 }}>{children}</span>
      {action}
    </div>
  );
}

function ChatHeader({ subject, ui, accent, dir, thread, onJumpToTask, onNewSession }) {
  const isWg = subject.kind === 'workgroup';
  const PROFILES = window.MOCK.PROFILES;
  const hubColor = isWg ? PROFILES.find(p => p.id === subject.hub)?.color : null;
  return (
      <div style={{
        padding: 'var(--hero-pad-top) var(--pane-pad-x) var(--hero-pad-bottom)',
        borderBottom: '.5px solid var(--line)',
        position: 'relative'
      }}>
      <div className="row between" style={{ alignItems: 'flex-end' }}>
        <div className="col" style={{ gap: 8, flex: 1, minWidth: 0 }}>
          <div className="row row-gap" style={{ gap: 12 }}>
            {isWg ?
            <span className="hash" style={{ fontSize: 28, fontWeight: 500, color: 'var(--ink-4)', lineHeight: 'var(--lh-tight)' }}>#</span> :

            <span className="diamond" style={{ '--c': subject.color, width: 14, height: 14, transform: 'rotate(45deg)' }} />
            }
            <h1 className="display" style={{
              margin: 0,
              fontSize: 28, fontWeight: 'var(--display-weight)',
              fontStyle: 'var(--display-italic)',
              color: 'var(--ink)',
              letterSpacing: '-0.018em'
            }}>{subject.id}</h1>
            <span className="mono" style={{ color: 'var(--ink-4)', fontSize: 11, marginLeft: 2, alignSelf: 'flex-end', paddingBottom: 4 }}>
              {isWg ? 'workgroup' : 'profile'}
            </span>
          </div>

          <div className="row row-gap" style={{ gap: 14, color: 'var(--ink-3)', fontSize: 12, flexWrap: 'wrap' }}>
            {isWg ?
            <> 
                <span className="row row-gap" style={{ gap: 5 }}>
                  <span style={{ color: 'var(--ink-4)' }}>hub</span>
                  <span className="diamond" style={{ '--c': PROFILES.find((p) => p.id === subject.hub)?.color, width: 7, height: 7 }} />
                  <span className="mono" style={{ color: 'var(--ink-2)' }}>@{subject.hub}</span>
                </span>
                <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
                <span><span style={{ color: 'var(--ink-4)' }}>members</span> <span className="mono tnum" style={{ color: 'var(--ink-2)' }}>{subject.members.length}</span></span>
                <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
                <MeterChip
                  value={<>${subject.budget.used.toFixed(2)}<span style={{ color: 'var(--ink-3)' }}>/${subject.budget.cap.toFixed(2)}</span></>}
                  pct={subject.budget.used / subject.budget.cap}
                  color={subject.color}
                  tip={`Workgroup budget — spent $${subject.budget.used.toFixed(2)} of $${subject.budget.cap.toFixed(2)} cap`}
                />
                {subject.status === 'paused' &&
              <>
                    <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
                    <span className="tag" style={{ background: 'color-mix(in srgb, #d4b443 18%, var(--bg-pane))', color: '#8a6b1a' }}>paused</span>
                  </>
              }
              </>
            :

            <> 
                <span className="mono" style={{ color: 'var(--ink-2)' }}>{subject.model}</span>
                {subject.contextSize != null && (
                  <>
                    <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
                    <MeterChip
                      value={<>{formatTokens(subject.contextUsed || 0)}<span style={{ color: 'var(--ink-3)' }}>/{formatTokens(subject.contextSize)}</span></>}
                      pct={(subject.contextUsed || 0) / subject.contextSize}
                      color={subject.color}
                      tip={`Context window — ${formatTokens(subject.contextUsed || 0)} of ${formatTokens(subject.contextSize)} tokens in use`}
                    />
                  </>
                )}
                {subject.budget != null && (
                  <>
                    <span style={{ width: 1, height: 10, background: 'var(--line-2)' }} />
                    <MeterChip
                      value={<>${(subject.used ?? 0).toFixed(2)}<span style={{ color: 'var(--ink-3)' }}>/${subject.budget.toFixed(2)}</span></>}
                      pct={(subject.used ?? 0) / subject.budget}
                      color={subject.color}
                      tip={`Daily budget — spent ${((subject.used ?? 0)).toFixed(2)} of $${subject.budget.toFixed(2)} cap today`}
                    />
                  </>
                )}
              </>
            }
          </div>
        </div>

        <div className="row row-gap" style={{ gap: 2 }}>
          {!isWg && (
            <>
              <SessionsButton profileId={subject.id} onNew={onNewSession} onPick={() => {}} />
              <span style={{ width: 1, height: 18, background: 'var(--line)', margin: '0 4px' }} />
            </>
          )}
          {isWg && (
            <>
              <TasksButton thread={thread} hubColor={hubColor} onJump={onJumpToTask} />
              <span style={{ width: 1, height: 18, background: 'var(--line)', margin: '0 4px' }} />
            </>
          )}
          {isWg &&
          <button className="btn btn-ghost" onClick={() => ui.toggleWgPause?.(subject.id)} title="Pause workgroup">
              {subject.status === 'paused' ? <window.I.Play /> : <window.I.Pause />}
              <span>{subject.status === 'paused' ? 'Resume' : 'Pause'}</span>
            </button>
          }
          {!isWg && <>
            <window.Tip text="Skills" side="r">
              <button className="iconbtn" onClick={() => ui.openPanel('skills')}>
                <window.I.Spark />
              </button>
            </window.Tip>
            <window.Tip text="Memory" side="r">
              <button className="iconbtn" onClick={() => ui.openPanel('memory')}>
                <window.I.Folder />
              </button>
            </window.Tip>
            <window.Tip text="Tools" side="r">
              <button className="iconbtn" onClick={() => ui.openPanel('tools')}>
                <window.I.Cpu />
              </button>
            </window.Tip>
            <span style={{ width: 1, height: 18, background: 'var(--line)', margin: '0 4px' }} />
          </>}
          <window.Tip text={`${isWg ? 'Workgroup' : 'Profile'} settings`} side="r">
            <button className="iconbtn" onClick={() => ui.openSettingsFor(subject)}>
              <window.I.Gear />
            </button>
          </window.Tip>
          <window.Tip text="Refresh thread" side="r">
            <button className="iconbtn"><window.I.Refresh /></button>
          </window.Tip>
        </div>
      </div>

      {/* underline accent — color stripe at the bottom */}
      <span style={{
        position: 'absolute', left: 32, bottom: -0.5, height: 1.5,
        width: 40, background: subject.color
      }} />
    </div>);

}

function Composer({ subject, accent, onSend, mentions, dir, disabled = false, disabledReason }) {
  const [text, setText] = useStateChat('');
  const taRef = useRefChat(null);
  const [mentionOpen, setMentionOpen] = useStateChat(false);
  const [mentionQuery, setMentionQuery] = useStateChat('');
  const [mentionIdx, setMentionIdx] = useStateChat(0);

  // Detect @mention trigger — only in workgroups
  const isWg = subject.kind === 'workgroup';
  const candidates = useMemoChat(() => {
    if (!isWg || !mentionOpen) return [];
    const members = subject.members.map(id => window.MOCK.PROFILES.find(p => p.id === id)).filter(Boolean);
    const q = mentionQuery.toLowerCase();
    return q ? members.filter(m => m.id.toLowerCase().startsWith(q)) : members;
  }, [isWg, mentionOpen, mentionQuery, subject]);
  const PROFILES = window.MOCK.PROFILES;
  const hubProfile = isWg ? PROFILES.find(p => p.id === subject.hub) : null;

  useEffectChat(() => {
    if (!taRef.current) return;
    taRef.current.style.height = 'auto';
    taRef.current.style.height = Math.min(180, taRef.current.scrollHeight) + 'px';
  }, [text]);

  const send = () => {
    if (!text.trim()) return;
    onSend(text);
    setText('');
  };

  return (
    <div style={{
      padding: 'var(--composer-pad-top) var(--pane-pad-x) var(--composer-pad-bottom)',
      background: 'var(--bg-pane)',
      borderTop: '.5px solid var(--line)'
    }}>
      <div style={{ maxWidth: 'var(--composer-max)', margin: '0 auto', opacity: disabled ? 0.6 : 1, pointerEvents: disabled ? 'none' : 'auto', position: 'relative' }}>
      {mentionOpen && candidates.length > 0 && (
        <div className="anim-pop" style={{
          position: 'absolute', bottom: 'calc(100% + 6px)', left: 0,
          width: 260, background: 'var(--bg-elev)',
          border: '.5px solid var(--line-2)', borderRadius: 12,
          boxShadow: 'var(--shadow)', zIndex: 30, padding: 4,
        }}>
          {candidates.map((c, i) => {
            const sel = i === mentionIdx;
            return (
              <button
                key={c.id}
                onClick={() => {
                  setText(t => t.replace(/(^|\s)@[a-z0-9_-]*$/i, (full, prefix) => `${prefix}@${c.id} `));
                  setMentionOpen(false);
                  taRef.current?.focus();
                }}
                className="row"
                style={{
                  width: '100%', padding: '6px 10px', borderRadius: 6, gap: 10,
                  background: sel ? 'var(--selected)' : 'transparent',
                  textAlign: 'left', alignItems: 'center',
                }}
                onMouseEnter={() => setMentionIdx(i)}
              >
                <span className="diamond" style={{ '--c': c.color, width: 8, height: 8 }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, flex: 1 }}>@{c.id}</span>
                {c.id === subject.hub && <span className="tag">hub</span>}
              </button>
            );
          })}
        </div>
      )}
      <div style={{
        borderRadius: 16,
        background: 'var(--bg-input)',
        border: '.5px solid var(--line-2)',
        padding: '14px 16px 10px',
        transition: 'border-color .12s'
      }}
      onFocus={(e) => { if (!disabled) e.currentTarget.style.borderColor = 'color-mix(in srgb, var(--ink) 25%, transparent)'; }}
      onBlur={(e) => e.currentTarget.style.borderColor = 'var(--line-2)'}>
        
        <textarea
          ref={taRef}
          value={text}
          disabled={disabled}
          onChange={(e) => {
            const v = e.target.value;
            setText(v);
            if (isWg) {
              // Detect @ trigger: @ at start or after whitespace, with optional handle prefix
              const match = v.match(/(^|\s)@([a-z0-9_-]*)$/i);
              if (match) {
                setMentionOpen(true);
                setMentionQuery(match[2]);
                setMentionIdx(0);
              } else {
                setMentionOpen(false);
              }
            }
          }}
          onKeyDown={(e) => {
            if (mentionOpen && candidates.length > 0) {
              if (e.key === 'ArrowDown') { e.preventDefault(); setMentionIdx(i => Math.min(candidates.length - 1, i + 1)); return; }
              if (e.key === 'ArrowUp')   { e.preventDefault(); setMentionIdx(i => Math.max(0, i - 1));                  return; }
              if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                const pick = candidates[mentionIdx];
                if (pick) setText(t => t.replace(/(^|\s)@[a-z0-9_-]*$/i, (full, prefix) => `${prefix}@${pick.id} `));
                setMentionOpen(false);
                return;
              }
              if (e.key === 'Escape') { setMentionOpen(false); return; }
            }
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(); }
          }}
          placeholder={
          disabled ? (disabledReason || '') :
          isWg ?
          `Direct @${subject.hub} — your input becomes a #task` :
          `Message ${subject.id}…`
          }
          style={{
            width: '100%', minHeight: 22,
            border: 0, background: 'transparent',
            resize: 'none', outline: 'none',
            color: 'var(--ink)', font: 'inherit',
            lineHeight: 'var(--lh-normal)'
          }} />
        
        <div className="row between" style={{ marginTop: 8 }}>
          <div className="row row-gap" style={{ gap: 10, color: 'var(--ink-3)', fontSize: 11, whiteSpace: 'nowrap' }}>
            {isWg ? (
              <span className="row row-gap" style={{ gap: 5 }}>
                <span style={{ color: 'var(--ink-4)' }}>→</span>
                <span className="diamond" style={{ '--c': hubProfile?.color, width: 7, height: 7 }} />
                <span><span className="mono" style={{ color: 'var(--ink-2)' }}>@{subject.hub}</span> formulates as <span className="mono" style={{ color: 'var(--ink-2)' }}>#task</span></span>
              </span>
            ) : (
              <span><span className="mono" style={{ color: 'var(--ink-2)' }}>@</span> mention</span>
            )}
            <span className="row row-gap" style={{ gap: 3 }}><span className="kbd">⌘</span><span className="kbd">↵</span> send</span>
          </div>
          <div className="row row-gap" style={{ gap: 6 }}>
            {!isWg &&
            <ModelPicker currentModel={subject.model} accent={accent} />
            }
            <button
              onClick={send}
              disabled={!text.trim()}
              className="iconbtn"
              style={{
                width: 30, height: 30, borderRadius: 10,
                background: text.trim() ? (isWg ? hubProfile?.color : accent) : 'var(--line)',
                color: text.trim() ? '#fff' : 'var(--ink-3)',
                cursor: text.trim() ? 'pointer' : 'default'
              }}
              title={isWg ? 'Open task' : 'Send'}>
              
              <window.I.Send style={{ width: 14, height: 14, strokeWidth: 2 }} />
            </button>
          </div>
        </div>
      </div>
      </div>
    </div>);

}

// Needs-provider empty state — shown when a profile has no model configured.
function NeedsProviderState({ subject, ui }) {
  return (
    <div className="col" style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 22, padding: '0 32px' }}>
      <span className="alpi-mark" style={{ width: 80, height: 80, color: subject.color, opacity: 0.9 }} />
      <div className="col" style={{ alignItems: 'center', gap: 8, textAlign: 'center', textWrap: 'pretty' }}>
        <h2 className="display" style={{
          margin: 0, fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em',
        }}>@{subject.id} needs a provider</h2>
        <p style={{ margin: 0, fontSize: 14, color: 'var(--ink-3)', lineHeight: 'var(--lh-normal)', fontFamily: 'var(--font-mono)' }}>
          Add an LLM provider (cloud or local Ollama) to start chatting.
        </p>
      </div>
      <button
        className="btn btn-primary"
        onClick={() => ui.openPanel('providers')}
        style={{ height: 40, padding: '0 20px', fontSize: 14 }}
      >Set up provider</button>
    </div>
  );
}

function ChatView({ state, ui }) {
  const { activeKind, activeId, dir, threads, setThread } = state;
  const PROFILES = window.MOCK.PROFILES;  const WORKGROUPS = window.MOCK.WORKGROUPS;

  const subject = useMemoChat(() => {
    if (activeKind === 'profile') {
      const p = PROFILES.find((x) => x.id === activeId);
      return p ? { ...p, kind: 'profile' } : null;
    }
    if (activeKind === 'workgroup') {
      const w = WORKGROUPS.find((x) => x.id === activeId);
      return w ? { ...w, kind: 'workgroup' } : null;
    }
    return null;
  }, [activeKind, activeId]);

  if (!subject) return null;
  const accent = subject.color;
  const needsProvider = subject.kind === 'profile' && !subject.model;

  const key = `${activeKind}:${activeId}`;
  const thread = threads[key] || (
    activeId === 'doc' ? window.MOCK.DOC_THREAD :
    activeId === 'customers' ? window.MOCK.CUSTOMERS_THREAD :
    activeId === 'architecture' ? window.MOCK.ARCHITECTURE_THREAD :
    []
  );

  const scrollRef = useRefChat(null);
  const [searchOpen, setSearchOpen] = useStateChat(false);
  const [showJump, setShowJump] = useStateChat(false);
  useEffectChat(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [thread.length]);

  // Track scroll position — show "jump to latest" pill when > 200px from bottom
  useEffectChat(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      setShowJump(distance > 200);
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener('scroll', onScroll);
  }, [thread.length]);

  const jumpToLatest = () => {
    if (scrollRef.current) scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  };

  useEffectChat(() => {
    const onKey = (e) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const jumpToTask = (taskId) => {
    const el = document.getElementById(`task-${taskId}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const isWorkgroup = subject.kind === 'workgroup';
  const hubColor = isWorkgroup ? PROFILES.find(p => p.id === subject.hub)?.color : null;

  const onSend = (text) => {
    if (subject.kind === 'workgroup') {
      // User doesn't chat in workgroups — the hub formulates the input as a #task.
      const slug = text.toLowerCase().slice(0, 40).trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      setThread(key, [...thread, {
        id: Date.now(), from: subject.hub, kind: 'agent', marker: 'task',
        taskId: slug || `task-${Date.now() % 1000}`,
        taskTitle: text.slice(0, 60),
        text: `Investigando: "${text.trim()}" — buscando fuentes primarias y patrones aplicables.`,
      }]);
      return;
    }
    const next = [...thread,
      { id: Date.now(), from: 'me', kind: 'user', text }
    ];
    setThread(key, next);
    setTimeout(() => {
      setThread(key, [...next, {
        id: Date.now() + 1, from: subject.id,
        kind: 'agent', tokens: 1200 + Math.floor(Math.random() * 4000), cost: +(Math.random() * 0.04).toFixed(4),
        text: `Noted. Thinking about it now — give me a minute.`,
      }]);
    }, 700);
  };

  return (
    <div className="col" style={{ height: '100%', minWidth: 0 }}>
      {needsProvider ? (
        <>
          <ChatHeader subject={subject} ui={ui} accent={accent} dir={dir} thread={[]} onJumpToTask={() => {}} onNewSession={() => {}} />
          <NeedsProviderState subject={subject} ui={ui} />
        </>
      ) : (<>
      {state.daemonOffline && (
        <Banner kind="danger" action={
          <button className="alink" style={{ color: 'var(--c-danger)' }}>Retry</button>
        }>
          <strong style={{ fontWeight: 600 }}>Local daemon unreachable.</strong>{' '}
          <span style={{ color: 'var(--ink-2)' }}>Reconnecting in 2s…</span>
        </Banner>
      )}
      {!state.daemonOffline && isWorkgroup && subject.status === 'paused' && (
        <Banner kind="warning">
          <strong style={{ fontWeight: 600 }}>This workgroup is paused.</strong>{' '}
          <span style={{ color: 'var(--ink-2)' }}>New messages won't fire. Resume from the header to continue.</span>
        </Banner>
      )}
      <ChatHeader subject={subject} ui={ui} accent={accent} dir={dir} thread={thread} onJumpToTask={jumpToTask} onNewSession={() => setThread(key, [])} />

      <div style={{ position: 'relative', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <window.SearchBar open={searchOpen} onClose={() => setSearchOpen(false)} scrollRef={scrollRef} />
        {showJump && (
          <button
            onClick={jumpToLatest}
            className="anim-pop"
            style={{
              position: 'absolute', right: 24, bottom: 14, zIndex: 30,
              width: 36, height: 36, borderRadius: 18,
              background: 'var(--bg-elev)', color: 'var(--ink-2)',
              border: '.5px solid var(--line-2)', boxShadow: 'var(--shadow)',
              display: 'grid', placeItems: 'center',
            }}
            title="Scroll to latest"
          >
            <svg viewBox="0 0 16 16" style={{ width: 14, height: 14, stroke: 'currentColor', fill: 'none', strokeWidth: 2 }}>
              <path d="M4 6l4 4 4-4"/>
            </svg>
          </button>
        )}
      <div ref={scrollRef} className="scroll" style={{ flex: 1, padding: 'var(--stream-pad-top) var(--pane-pad-x) var(--stream-pad-bottom)' }}>
        <div className="col" style={{ gap: 24, maxWidth: 'var(--stream-max)', margin: '0 auto' }}>
          {thread.map((m, i) => {
            const isUser = m.kind === 'user' || m.from === 'me';
            const fromProfile = isUser ? null : PROFILES.find((p) => p.id === m.from) || subject;
            const isHub = isWorkgroup && !isUser && fromProfile?.id === subject.hub;
            return (
              <Message
                key={m.id}
                m={m}
                profile={fromProfile}
                isUser={isUser}
                isHub={isHub}
                hubColor={hubColor}
                subject={subject}
                accent={accent}
                onJumpToTask={jumpToTask}
              />
            );
          })}
          {thread.length === 0 &&
          <div className="col anim-fade" style={{ alignItems: 'center', gap: 16, marginTop: 64, color: 'var(--ink-3)' }}>
              {isWorkgroup ? (
                <span className="display" style={{ fontSize: 56, fontWeight: 500, color: 'var(--ink-4)', lineHeight: 'var(--lh-tight)', fontFamily: 'var(--font-mono)' }}>#</span>
              ) : (
                <span className="alpi-mark" style={{ width: 56, height: 56, color: accent, opacity: 0.9 }} />
              )}
              <div className="display" style={{ fontSize: 22, textAlign: 'center' }}>
                {isWorkgroup ? `direct #${subject.id}` : `start a thread with ${subject.id}`}
              </div>
              <div className="mono" style={{ fontSize: 11, textAlign: 'center', maxWidth: 420 }}>
                {isWorkgroup ?
                  <>{`${subject.members.length} members · hub @${subject.hub} · your input opens a #task`}</> :
                  <>{`${subject.model || ''}`}</>
                }
              </div>
            </div>
          }
        </div>
      </div>
      </div>

      <Composer
        subject={subject} accent={accent} onSend={onSend} dir={dir}
        disabled={state.daemonOffline || (isWorkgroup && subject.status === 'paused')}
        disabledReason={state.daemonOffline ? "Daemon offline — can't send" : "Workgroup paused"}
      />
      </>)}
    </div>);

}

// New chat / empty state — composer-first scaffold.
// No hero text. Profile picker lives at TOP of composer (identity is protagonist).
// Recents below (real session previews). Fallback to suggestion chips if no recents.
function NewChatView({ state, ui }) {
  const PROFILES = window.MOCK.PROFILES;
  const [pick, setPick] = useStateChat('alpi');
  const accent = PROFILES.find((p) => p.id === pick)?.color;
  const [text, setText] = useStateChat('');
  const [pickerOpen, setPickerOpen] = useStateChat(false);
  const [query, setQuery] = useStateChat('');
  const pickerRef = useRefChat(null);

  useEffectChat(() => {
    if (!pickerOpen) return;
    const onDoc = (e) => { if (!pickerRef.current?.contains(e.target)) setPickerOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [pickerOpen]);

  const filtered = PROFILES.filter((p) => p.id.includes(query.toLowerCase()));
  const picked = PROFILES.find(p => p.id === pick);

  const start = () => {
    if (!text.trim()) return;
    state.setThread(`profile:${pick}`, [
      { id: Date.now(), from: 'me', kind: 'user', text }
    ]);
    ui.openChat({ kind: 'profile', id: pick });
    setTimeout(() => {
      state.setThread(`profile:${pick}`, [
        { id: Date.now(), from: 'me', kind: 'user', text },
        { id: Date.now() + 1, from: pick, kind: 'agent', tokens: 1400, cost: 0.01, text: `Working on it — give me a second.` }
      ]);
    }, 700);
  };

  // Mock recents — last sessions, day-grouped flat list
  const recents = [
    { profileId: 'doc',   preview: '@peer como ves las vitaminas que tomo?',         when: '22m', turns: 8 },
    { profileId: 'builder', preview: 'Refactor this PR for clarity',                 when: '2h',  turns: 18 },
    { profileId: 'vera',  preview: 'What should we stop doing this quarter?',        when: '4h',  turns: 11 },
    { profileId: 'doc',   preview: "Plan tonight before tomorrow's 6am run",         when: '7h',  turns: 12 },
  ];

  const openRecent = (r) => {
    ui.openChat({ kind: 'profile', id: r.profileId });
  };

  return (
    <div className="col" style={{ height: '100%', minWidth: 0, paddingTop: 38 }}>
      <div className="col center" style={{ flex: 1, padding: '0 32px' }}>
        <div className="col" style={{ alignItems: 'stretch', gap: 24, width: 'min(640px, 100%)' }}>

          <span className="alpi-mark" style={{ width: 64, height: 64, alignSelf: 'center', opacity: 0.85, color: 'var(--ink-3)' }} />

          {/* Composer — profile picker integrated at top */}
          <div style={{
            background: 'var(--bg-input)',
            border: '.5px solid var(--line-2)',
            borderRadius: 14,
            boxShadow: 'var(--shadow-sm)',
            overflow: 'visible',
            position: 'relative',
          }}>
            {/* Header — to: @alpi · model · ▼ */}
            <div style={{ position: 'relative', borderBottom: '.5px solid var(--line)' }} ref={pickerRef}>
              <button
                onClick={() => setPickerOpen(o => !o)}
                className="row row-gap"
                style={{
                  width: '100%', padding: '10px 14px', gap: 10,
                  background: 'transparent', textAlign: 'left',
                  borderRadius: '14px 14px 0 0',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--hover)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <span style={{ fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '.06em' }}>to</span>
                <span className="diamond" style={{ '--c': accent, width: 9, height: 9 }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 500 }}>@{pick}</span>
                <span style={{ color: 'var(--ink-4)' }}>·</span>
                <span className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>{picked?.model || ''}</span>
                <span style={{ flex: 1 }} />
                <window.I.ChevDown style={{ color: 'var(--ink-3)' }} />
              </button>
              {pickerOpen && (
                <div className="anim-pop" style={{
                  position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
                  background: 'var(--bg-elev)',
                  border: '.5px solid var(--line-2)', borderRadius: 12,
                  boxShadow: 'var(--shadow)', padding: 6, zIndex: 50,
                }}>
                  <input
                    value={query} onChange={(e) => setQuery(e.target.value)}
                    placeholder="Find alpi…"
                    autoFocus
                    className="field"
                    style={{ height: 30, padding: '0 10px', fontSize: 12, marginBottom: 4 }}
                  />
                  <div className="scroll" style={{ maxHeight: 260 }}>
                    {filtered.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => { setPick(p.id); setPickerOpen(false); setQuery(''); }}
                        className="row row-gap"
                        style={{
                          width: '100%', padding: '8px 10px', borderRadius: 8,
                          background: pick === p.id ? 'var(--selected)' : 'transparent',
                          textAlign: 'left',
                        }}
                        onMouseEnter={(e) => { if (pick !== p.id) e.currentTarget.style.background = 'var(--hover)'; }}
                        onMouseLeave={(e) => { if (pick !== p.id) e.currentTarget.style.background = 'transparent'; }}
                      >
                        <span className="diamond" style={{ '--c': p.color }} />
                        <span style={{ flex: 1, fontSize: 13 }}>@{p.id}</span>
                        <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>{p.model.split('/')[1]}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Body — textarea + send */}
            <div style={{ padding: '14px 16px 10px' }}>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); start(); } }}
                placeholder={`Message @${pick}…`}
                autoFocus
                style={{ width: '100%', minHeight: 56, border: 0, background: 'transparent', resize: 'none', outline: 'none', font: 'inherit', color: 'var(--ink)', lineHeight: 'var(--lh-normal)' }}
              />
              <div className="row between" style={{ marginTop: 6 }}>
                <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                  <span className="kbd">⌘</span><span className="kbd" style={{ marginLeft: 2 }}>↵</span> to send
                </span>
                <button
                  onClick={start}
                  className="iconbtn"
                  disabled={!text.trim()}
                  style={{
                    width: 30, height: 30, borderRadius: 10,
                    background: text.trim() ? accent : 'var(--line)',
                    color: text.trim() ? '#fff' : 'var(--ink-3)',
                    cursor: text.trim() ? 'pointer' : 'default',
                  }}
                ><window.I.Send style={{ width: 14, height: 14, strokeWidth: 2 }} /></button>
              </div>
            </div>
          </div>

          {/* Recents — real sessions, not generic suggestions */}
          {recents.length > 0 && (
            <div className="col" style={{ gap: 8 }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span className="eyebrow">Recents</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--ink-4)' }}>{recents.length} sessions</span>
              </div>
              <div className="col" style={{ gap: 1 }}>
                {recents.map((r, i) => {
                  const p = PROFILES.find(x => x.id === r.profileId);
                  return (
                    <button
                      key={i}
                      onClick={() => openRecent(r)}
                      className="row row-gap"
                      style={{
                        width: '100%', padding: '8px 10px', borderRadius: 8,
                        background: 'transparent', textAlign: 'left', gap: 10,
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'var(--hover)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      <span className="diamond" style={{ '--c': p?.color, width: 8, height: 8 }} />
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--ink-3)', minWidth: 56 }}>@{r.profileId}</span>
                      <span style={{
                        flex: 1, fontSize: 13, color: 'var(--ink-2)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{r.preview}</span>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--ink-4)', flexShrink: 0 }}>{r.when}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

window.ChatView = ChatView;
window.NewChatView = NewChatView;
window.ModelPicker = ModelPicker;
