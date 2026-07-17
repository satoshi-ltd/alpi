/* wireframe-kit.jsx — low-fi wireframe primitives + 4 style "vibes".
   Everything is grayscale + ONE accent per style. Typography & spacing carry
   the style hint. Annotations are handwritten (Caveat). Exports to window. */

// ── Style tokens ────────────────────────────────────────────────
const STYLES = {
  boutique: {
    key: 'boutique', label: 'Boutique',
    head: "'Cormorant Garamond', Georgia, serif",
    body: "'Jost', system-ui, sans-serif",
    accent: '#9c6a45', accent2: '#6f4e34', accentSoft: '#ece3da',
    ink: '#2c2722', muted: '#8a8178', line: '#d8d0c6', fill: '#ece8e2',
    paper: '#fbf9f6',
    radius: 0, gap: 30, pad: 40, headWeight: 500, tracking: '0.18em',
    upper: true, btnRadius: 0,
  },
  budget: {
    key: 'budget', label: 'Budget',
    head: "'Archivo', system-ui, sans-serif",
    body: "'Archivo', system-ui, sans-serif",
    accent: '#1f6feb', accent2: '#1850c4', accentSoft: '#e3edfd', price: '#1f8a4c',
    ink: '#22262b', muted: '#7b8290', line: '#dde1e7', fill: '#eef1f5',
    paper: '#ffffff',
    radius: 6, gap: 14, pad: 18, headWeight: 800, tracking: '-0.01em',
    upper: false, btnRadius: 6,
  },
  business: {
    key: 'business', label: 'Business',
    head: "'Libre Franklin', system-ui, sans-serif",
    body: "'Libre Franklin', system-ui, sans-serif",
    accent: '#1e3a5f', accent2: '#36577e', accentSoft: '#e7ecf2',
    ink: '#1d242e', muted: '#737d89', line: '#d5dae1', fill: '#eceff3',
    paper: '#ffffff',
    radius: 3, gap: 22, pad: 28, headWeight: 700, tracking: '-0.005em',
    upper: false, btnRadius: 3,
  },
  resort: {
    key: 'resort', label: 'Resort',
    head: "'Quicksand', system-ui, sans-serif",
    body: "'Quicksand', system-ui, sans-serif",
    accent: '#0d8a8a', accent2: '#e8943a', accentSoft: '#d8f0ee', sun: '#e8943a',
    ink: '#1c2e2c', muted: '#6f8582', line: '#cfe0dd', fill: '#e2efec',
    paper: '#f7fbfa',
    radius: 18, gap: 26, pad: 30, headWeight: 700, tracking: '0',
    upper: false, btnRadius: 999,
  },
};

const SCtx = React.createContext(STYLES.boutique);
const useS = () => React.useContext(SCtx);

// ── Bindings layer ─────────────────────────────────────────────
// Every dynamic slot can declare a `bind` (e.g. "hero.title"). When the global
// toggle is on, a small monospace badge surfaces the binding key so the agent
// network knows exactly what content feeds each slot. Off = clean production look.
const BindCtx = React.createContext(false);
const useBind = () => React.useContext(BindCtx);

function hexA(h, a) {
  if (typeof h !== 'string' || h[0] !== '#') return h;
  let c = h.slice(1);
  if (c.length === 3) c = c.split('').map((x) => x + x).join('');
  const n = parseInt(c, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function BindBadge({ name, corner, light }) {
  const s = useS();
  const pos = corner ? { top: 6, left: 6 } : { top: -13, left: 0 };
  return (
    <span style={{ position: 'absolute', ...pos, zIndex: 6, fontFamily: 'ui-monospace, Menlo, monospace',
      fontSize: 9.5, fontWeight: 600, background: light ? '#fff' : s.accent, color: light ? s.accent : '#fff',
      padding: '1px 6px', borderRadius: 4, letterSpacing: '.01em', whiteSpace: 'nowrap',
      boxShadow: '0 1px 4px rgba(0,0,0,.28)', pointerEvents: 'none' }}>{name}</span>
  );
}

// Inline binding wrapper (prices, names, ratings…) — outline doesn't shift layout.
function B({ b, children, style }) {
  const show = useBind();
  const s = useS();
  if (!show || !b) return children;
  return (
    <span style={{ position: 'relative', outline: `1px dashed ${hexA(s.accent, 0.7)}`, outlineOffset: 2,
      borderRadius: 2, ...style }}>{children}<BindBadge name={b} /></span>
  );
}

// Curated placeholder copy so paragraphs read like a real site, not gray bars.
const COPY = [
  'Wake to the sound of the sea and a slow, unhurried morning.',
  'Each room is finished with natural materials and quiet, considered detail.',
  'Our table celebrates the day\u2019s catch and produce from the gardens nearby.',
  'Steps from the old town, yet a world away from its noise and hurry.',
  'A handful of rooms, a single promise: rest, beautifully kept.',
  'Sunlight moves across whitewashed walls through the long afternoon.',
  'Linen sheets, deep baths and windows that open to the breeze.',
  'Stay a while and the place reveals itself, one quiet corner at a time.',
  'Thoughtful service that anticipates rather than intrudes on your day.',
  'From breakfast on the terrace to a last glass of wine by the water.',
  'Comfortable, well connected and made for the way you travel now.',
  'Every detail is chosen to make the simple things feel generous.',
];
let _copyI = 0;

// ── Page shell ─────────────────────────────────────────────────
// Fills the artboard height exactly; trailing spacer absorbs slack so the
// card bottom is clean. Keep content density within the artboard height.
function Page({ styleKey, children }) {
  const s = STYLES[styleKey];
  const show = !!window.__SHOW_BINDINGS;
  return (
    <SCtx.Provider value={s}>
      <BindCtx.Provider value={show}>
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column',
          background: s.paper, fontFamily: s.body, color: s.ink, overflow: 'hidden' }}>
          {children}
          <div style={{ flex: '1 1 auto', minHeight: 0 }} />
        </div>
      </BindCtx.Provider>
    </SCtx.Provider>
  );
}

// ── Primitives ─────────────────────────────────────────────────
function Box({ h, w, fill, radius, br, style, children }) {
  const s = useS();
  return (
    <div style={{ height: h, width: w, background: fill ?? s.fill,
      borderRadius: radius ?? s.radius, border: br ? `1px solid ${s.line}` : 'none',
      boxSizing: 'border-box', ...style }}>{children}</div>
  );
}

// Image placeholder — tonal washes (reads as a photo), renders children
// (hero overlays), auto-scrim when children present, optional binding badge.
let _phSeed = 0;
function Ph({ h, w = '100%', label, radius, style, tint, dark, bind, children }) {
  const s = useS();
  const seed = _phSeed++;
  const ang = 118 + (seed % 4) * 26;
  const a = tint || s.accent;
  const wash = `linear-gradient(${ang}deg, ${hexA(a, 0.22)}, ${hexA(s.ink, 0.05)} 55%, ${hexA(a, 0.12)})`;
  const hi = `radial-gradient(120% 85% at 22% 16%, ${hexA('#ffffff', 0.34)}, transparent 58%)`;
  const hasKids = React.Children.count(children) > 0;
  return (
    <div style={{ height: h, width: w, borderRadius: radius ?? s.radius, position: 'relative',
      overflow: 'hidden', background: `${hi}, ${wash}, ${s.fill}`, ...style }}>
      {!hasKids && (
        <svg width="38" height="29" viewBox="0 0 40 30" fill="none" stroke={hexA(s.ink, 0.28)} strokeWidth="1.5"
          style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)' }}>
          <rect x="1" y="1" width="38" height="28" rx="2" /><circle cx="11" cy="10" r="3.2" />
          <path d="M3 26l11-11 8 7 6-5 9 9" />
        </svg>
      )}
      {(hasKids || dark) && <div style={{ position: 'absolute', inset: 0,
        background: `linear-gradient(180deg, ${hexA('#000', 0.12)}, ${hexA('#000', 0.32)})` }} />}
      {children}
      {bind && <BindBadge name={bind} corner light={hasKids} />}
    </div>
  );
}

// Body copy. Was gray bars — now real placeholder prose clamped to ~n lines,
// in the style's body font. Keeps n / width / centered so call sites don't change.
function Lines({ n = 3, w = '100%', last, h, gap, style, bind, size = 13 }) {
  const s = useS();
  const centered = style && style.alignItems === 'center';
  const start = (_copyI += 3) % COPY.length;
  let txt = '';
  for (let i = 0; i <= n; i++) txt += COPY[(start + i) % COPY.length] + ' ';
  const { alignItems, ...rest } = style || {};
  const el = (
    <p style={{ width: w, margin: 0, fontFamily: s.body, fontSize: size, lineHeight: 1.6,
      color: s.muted, textAlign: centered ? 'center' : 'left', textWrap: 'pretty',
      display: '-webkit-box', WebkitLineClamp: n, WebkitBoxOrient: 'vertical', overflow: 'hidden', ...rest }}>
      {txt.trim()}
    </p>
  );
  const show = useBind();
  if (!show || !bind) return el;
  return <div style={{ position: 'relative', width: w }}>{el}<BindBadge name={bind} /></div>;
}

// Single paragraph alias (explicit copy or binding).
function P({ children, w, size = 13, muted = true, style, bind }) {
  const s = useS();
  const el = (
    <p style={{ width: w, margin: 0, fontFamily: s.body, fontSize: size, lineHeight: 1.6,
      color: muted ? s.muted : s.ink, textWrap: 'pretty', ...style }}>{children}</p>
  );
  const show = useBind();
  if (!show || !bind) return el;
  return <div style={{ position: 'relative', width: w }}>{el}<BindBadge name={bind} /></div>;
}

// Heading — REAL placeholder text in the style's display font (carries vibe)
function H({ children, size = 30, w, style, bind }) {
  const s = useS();
  const el = (
    <div style={{ fontFamily: s.head, fontSize: size, fontWeight: s.headWeight,
      lineHeight: 1.08, color: s.ink, letterSpacing: s.head === STYLES.boutique.head ? '0.01em' : s.tracking,
      maxWidth: w, textWrap: 'balance', ...style }}>{children}</div>
  );
  const show = useBind();
  if (!show || !bind) return el;
  return <div style={{ position: 'relative', display: 'inline-block', maxWidth: w }}>{el}<BindBadge name={bind} /></div>;
}

// Eyebrow / kicker label
function Kicker({ children, style, bind }) {
  const s = useS();
  const el = (
    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: s.upper ? s.tracking : '0.08em',
      textTransform: s.upper ? 'uppercase' : 'none', color: s.accent, fontFamily: s.body, ...style }}>{children}</div>
  );
  const show = useBind();
  if (!show || !bind) return el;
  return <div style={{ position: 'relative', display: 'inline-block' }}>{el}<BindBadge name={bind} /></div>;
}

function Btn({ children, solid = true, size = 'md', style }) {
  const s = useS();
  const pad = size === 'lg' ? '13px 26px' : size === 'sm' ? '7px 14px' : '10px 20px';
  const fs = size === 'lg' ? 14 : size === 'sm' ? 11 : 12.5;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      padding: pad, fontSize: fs, fontWeight: 600, fontFamily: s.body,
      letterSpacing: s.upper ? '0.12em' : '0.01em', textTransform: s.upper ? 'uppercase' : 'none',
      borderRadius: s.btnRadius, whiteSpace: 'nowrap',
      background: solid ? s.accent : 'transparent', color: solid ? '#fff' : s.accent2,
      border: solid ? 'none' : `1px solid ${s.accent2}`, ...style }}>{children}</span>
  );
}

function Chip({ children, accent, style }) {
  const s = useS();
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px',
      fontSize: 11, fontWeight: 600, fontFamily: s.body, borderRadius: s.radius ? 99 : 0,
      background: accent ? s.accentSoft : s.fill, color: accent ? s.accent : s.muted,
      border: `1px solid ${accent ? 'transparent' : s.line}`, ...style }}>{children}</span>
  );
}

function Stars({ n = 5, size = 11 }) {
  const s = useS();
  return (
    <span style={{ display: 'inline-flex', gap: 1, color: s.accent, fontSize: size }}>
      {Array.from({ length: n }).map((_, i) => <span key={i}>★</span>)}
    </span>
  );
}

// Language selector (globe + current lang + caret) — standard on hotel sites
function LangSelect({ dark, lang = 'EN' }) {
  const s = useS();
  const c = dark ? 'rgba(255,255,255,.9)' : s.muted;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, fontWeight: 600,
      fontFamily: s.body, color: c, cursor: 'pointer', whiteSpace: 'nowrap' }}>
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke={c} strokeWidth="1.2">
        <circle cx="6.5" cy="6.5" r="5.5" /><path d="M1 6.5h11M6.5 1c1.8 1.5 1.8 9.5 0 11M6.5 1c-1.8 1.5-1.8 9.5 0 11" />
      </svg>
      {lang}
      <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke={c} strokeWidth="1.3" strokeLinecap="round"><path d="M1.5 3l2.5 2.5L6.5 3" /></svg>
    </span>
  );
}

function Row({ children, gap, align = 'center', justify, wrap, style }) {
  const s = useS();
  return <div style={{ display: 'flex', gap: gap ?? s.gap, alignItems: align,
    justifyContent: justify, flexWrap: wrap ? 'wrap' : 'nowrap', ...style }}>{children}</div>;
}
function Col({ children, gap, style }) {
  const s = useS();
  return <div style={{ display: 'flex', flexDirection: 'column', gap: gap ?? 10, ...style }}>{children}</div>;
}
function Grid({ cols = 3, gap, children, style }) {
  const s = useS();
  return <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`,
    gap: gap ?? s.gap, ...style }}>{children}</div>;
}

// Section padding wrapper
function Sec({ children, pad, style }) {
  const s = useS();
  return <div style={{ padding: `0 ${pad ?? s.pad}px`, flexShrink: 0, ...style }}>{children}</div>;
}
function VGap({ h }) { return <div style={{ height: h, flexShrink: 0 }} />; }

// Handwritten annotation — hidden in production view (kept as no-op so the many
// existing <Note> call sites need no edits). Flip to render if you want the rationale back.
function Note() { return null; }

// Booking widget — varies by style via props. Fields show faint sample values.
function BookingBar({ fields = ['Check-in', 'Check-out', 'Guests'], cta = 'Search', vertical, style, bind }) {
  const s = useS();
  const sample = { 'Check-in': 'Add date', 'Check-out': 'Add date', 'Guests': '2 adults',
    'Rooms': '1 room', 'Dates': 'Add dates', 'Promo': 'Code' };
  const inner = (
    <div style={{ display: 'flex', flexDirection: vertical ? 'column' : 'row', gap: 10,
      background: '#fff', border: `1px solid ${s.line}`, borderRadius: s.radius ? s.radius + 4 : 0,
      padding: 12, alignItems: vertical ? 'stretch' : 'flex-end',
      boxShadow: s.key === 'boutique' ? 'none' : '0 6px 22px rgba(0,0,0,0.07)' }}>
      {fields.map((f, i) => (
        <div key={i} style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.04em', color: s.muted,
            textTransform: 'uppercase', marginBottom: 5 }}>{f}</div>
          <div style={{ height: 30, background: s.fill, borderRadius: s.radius, border: `1px solid ${s.line}`,
            display: 'flex', alignItems: 'center', padding: '0 10px', fontSize: 11.5, color: hexA(s.ink, 0.5) }}>
            {sample[f] || ''}</div>
        </div>
      ))}
      <Btn size={vertical ? 'md' : 'lg'} style={{ flexShrink: 0, height: vertical ? 'auto' : 49 }}>{cta}</Btn>
    </div>
  );
  const show = useBind();
  if (!show || !bind) return <div style={style}>{inner}</div>;
  return <div style={{ position: 'relative', ...style }}><BindBadge name={bind} corner />{inner}</div>;
}

// Top navigation — restyled per vibe
function Nav({ links = ['Rooms', 'Amenities', 'Dining', 'Contact'], cta = 'Book now', utility }) {
  const s = useS();
  const center = s.key === 'boutique';
  return (
    <div style={{ flexShrink: 0 }}>
      {utility && (
        <div style={{ background: s.ink, color: '#fff', display: 'flex', justifyContent: 'flex-end',
          gap: 18, padding: '6px 28px', fontSize: 10.5, letterSpacing: '0.02em', opacity: 0.92, alignItems: 'center' }}>
          <span>+1 555 0100</span><span>Sign in</span><LangSelect dark />
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center',
        flexDirection: center ? 'column' : 'row', gap: center ? 12 : 0,
        padding: center ? '20px 0 16px' : `14px ${s.pad}px`,
        borderBottom: `1px solid ${s.line}`, justifyContent: 'space-between' }}>
        <div style={{ fontFamily: s.head, fontSize: center ? 22 : 19, fontWeight: s.headWeight,
          letterSpacing: s.upper ? '0.22em' : s.tracking, textTransform: s.upper ? 'uppercase' : 'none' }}>
          HOTEL
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}>
          <div style={{ display: 'flex', gap: 20, fontSize: 12, color: s.muted, fontWeight: 500 }}>
            {links.map((l) => <span key={l}>{l}</span>)}
          </div>
          {!utility && <LangSelect />}
          {!center && <Btn size="sm">{cta}</Btn>}
        </div>
        {center && <div style={{ width: 70, height: 1, background: s.line }} />}
      </div>
    </div>
  );
}

function Footer({ cols = 4 }) {
  const s = useS();
  const groups = [
    ['Explore', ['Rooms', 'Amenities', 'Dining', 'Gallery']],
    ['Visit', ['Location', 'Offers', 'Journal', 'Contact']],
    ['Connect', ['Instagram', 'Newsletter', 'Press', 'Careers']],
  ];
  return (
    <div style={{ flexShrink: 0, marginTop: 'auto', background: s.key === 'boutique' ? s.paper : s.accentSoft,
      borderTop: `1px solid ${s.line}`, padding: `28px ${s.pad}px 24px` }}>
      <div style={{ display: 'grid', gridTemplateColumns: `1.5fr repeat(${cols - 1}, 1fr)`, gap: 24 }}>
        <div>
          <div style={{ fontFamily: s.head, fontSize: 17, fontWeight: s.headWeight,
            letterSpacing: s.upper ? '0.2em' : 0, textTransform: s.upper ? 'uppercase' : 'none', marginBottom: 10 }}>HOTEL</div>
          <P size={12} style={{ maxWidth: 230 }}>Calle del Puerto 4 · +1 555 0100 · hello@hotel.com</P>
        </div>
        {groups.slice(0, cols - 1).map(([title, items]) => (
          <div key={title}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.04em', textTransform: 'uppercase',
              color: s.ink, marginBottom: 10 }}>{title}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {items.map((it) => <span key={it} style={{ fontSize: 12, color: s.muted }}>{it}</span>)}
            </div>
          </div>
        ))}
      </div>
      <div style={{ borderTop: `1px solid ${s.line}`, marginTop: 22, paddingTop: 14, display: 'flex',
        justifyContent: 'space-between', fontSize: 11, color: s.muted }}>
        <span>© 2026 Hotel. All rights reserved.</span><span>Privacy · Terms</span>
      </div>
    </div>
  );
}

// Desktop browser chrome + Phone shell (visual wrappers)
function Browser({ children, h }) {
  const s = useS();
  return (
    <div style={{ height: h, display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <div style={{ flexShrink: 0, height: 30, background: '#e9e7e2', display: 'flex', alignItems: 'center',
        gap: 6, padding: '0 12px', borderBottom: '1px solid #dcd9d3' }}>
        {['#e06c5e', '#e3b34e', '#5fb868'].map((c) => (
          <span key={c} style={{ width: 9, height: 9, borderRadius: 99, background: c }} />
        ))}
        <div style={{ marginLeft: 10, flex: 1, height: 16, background: '#fff', borderRadius: 8,
          border: '1px solid #dcd9d3', fontSize: 9, color: '#aaa', display: 'flex', alignItems: 'center',
          padding: '0 9px' }}>hotel.com</div>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>{children}</div>
    </div>
  );
}

Object.assign(window, {
  STYLES, SCtx, useS, BindCtx, useBind, B, hexA, Page, Box, Ph, Lines, P, H, Kicker, Btn, Chip, Stars, LangSelect,
  Row, Col, Grid, Sec, VGap, Note, BookingBar, Nav, Footer, Browser,
});
