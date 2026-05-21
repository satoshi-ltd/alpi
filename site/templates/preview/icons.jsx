// icons.jsx — small icon set built from simple geometric primitives only.
// No hand-drawn complex SVGs.

const I = {
  Search: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5l3 3"/></svg>,
  Plus: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M8 3v10M3 8h10"/></svg>,
  Arrow: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M8 13V3M4 7l4-4 4 4"/></svg>,
  ArrowLeft: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M3 8h10M7 4L3 8l4 4"/></svg>,
  ArrowRight: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M3 8h10M9 4l4 4-4 4"/></svg>,
  Refresh: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M3 7a5 5 0 019.2-2.5M13 9a5 5 0 01-9.2 2.5M11 2v3h-3M5 14v-3h3"/></svg>,
  Sidebar: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><rect x="2" y="3" width="12" height="10" rx="2"/><path d="M6 3v10"/></svg>,
  Gear: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><circle cx="8" cy="8" r="2.2"/><path d="M8 2.2v1.6M8 12.2v1.6M2.2 8h1.6M12.2 8h1.6M4 4l1.1 1.1M10.9 10.9L12 12M4 12l1.1-1.1M10.9 5.1L12 4"/></svg>,
  Check: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M3 8l3.5 3.5L13 5"/></svg>,
  X: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M4 4l8 8M12 4l-8 8"/></svg>,
  Pause: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><rect x="4" y="3.5" width="2.5" height="9" rx="0.5"/><rect x="9.5" y="3.5" width="2.5" height="9" rx="0.5"/></svg>,
  Play: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M5 3l8 5-8 5z" fill="currentColor" stroke="none"/></svg>,
  Copy: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><rect x="5" y="5" width="8" height="8" rx="1.5"/><path d="M3 11V4a1 1 0 011-1h7"/></svg>,
  Help: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><circle cx="8" cy="8" r="6"/><path d="M6.4 6.2a1.7 1.7 0 113.2.6c0 1-.9 1.2-1.6 2v.4"/><circle cx="8" cy="11.5" r=".5" fill="currentColor" stroke="none"/></svg>,
  Cpu: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><rect x="3.5" y="3.5" width="9" height="9" rx="1.5"/><rect x="6" y="6" width="4" height="4" rx=".5"/><path d="M2 6h1.5M2 10h1.5M12.5 6H14M12.5 10H14M6 2v1.5M10 2v1.5M6 12.5V14M10 12.5V14"/></svg>,
  Wifi: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M2 5.5a9 9 0 0112 0M4 8a6 6 0 018 0M6 10.5a3 3 0 014 0"/><circle cx="8" cy="13" r=".7" fill="currentColor" stroke="none"/></svg>,
  Globe: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2C6 4 6 12 8 14"/></svg>,
  Sun: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><circle cx="8" cy="8" r="3"/><path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.3 3.3l1 1M11.7 11.7l1 1M3.3 12.7l1-1M11.7 4.3l1-1"/></svg>,
  Moon: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M12.5 9.5A5 5 0 016.5 3.5a5.5 5.5 0 106 6z"/></svg>,
  Auto: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><circle cx="8" cy="8" r="5.5"/><path d="M8 2.5v11"/></svg>,
  Trash: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M3 4h10M6 4V2.5h4V4M4.5 4l.6 9a1 1 0 001 1h3.8a1 1 0 001-1l.6-9"/></svg>,
  ChevDown: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M4 6l4 4 4-4"/></svg>,
  ChevRight: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M6 4l4 4-4 4"/></svg>,
  Send: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M8 13V3M4 7l4-4 4 4"/></svg>,
  Dollar: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M8 2v12M11 5.5C11 4 9.5 3 8 3s-3 .8-3 2.2c0 2.8 6 1.8 6 4.6 0 1.5-1.5 2.2-3 2.2s-3-1-3-2.5"/></svg>,
  Spark: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M8 2v3M8 11v3M2 8h3M11 8h3M4.5 4.5l1.7 1.7M9.8 9.8l1.7 1.7M4.5 11.5l1.7-1.7M9.8 6.2l1.7-1.7"/></svg>,
  Tag: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M2.5 8.5l6 6 6-6-6-6h-6z"/><circle cx="5.5" cy="5.5" r=".8"/></svg>,
  Folder: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M2 4.5A1.5 1.5 0 013.5 3H6l1.5 1.5h5A1.5 1.5 0 0114 6v6a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 012 12V4.5z"/></svg>,
  Eye: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M1.5 8C3 5 5.3 3.5 8 3.5S13 5 14.5 8C13 11 10.7 12.5 8 12.5S3 11 1.5 8z"/><circle cx="8" cy="8" r="2"/></svg>,
  MuteIcon: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M3 5h2.5L9 2.5v11L5.5 11H3z" stroke="currentColor" strokeWidth="1.5" fill="none"/><path d="M11 5l4 6M15 5l-4 6" stroke="currentColor" strokeWidth="1.5"/></svg>,
  Archive: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><rect x="2" y="3.5" width="12" height="3" rx=".5"/><path d="M3 6.5v6a1 1 0 001 1h8a1 1 0 001-1v-6M6.5 9h3"/></svg>,
  Bell: (p) => <svg viewBox="0 0 16 16" className="icon" {...p}><path d="M4 11V7a4 4 0 018 0v4l1 1.5H3z"/><path d="M6.5 13a1.5 1.5 0 003 0"/></svg>,
  Alpaca: (p) => (
    // tiny abstract: ear-ear-head — only circles/rounded rects, kept geometric
    <svg viewBox="0 0 40 40" {...p}>
      <circle cx="20" cy="22" r="11" fill="currentColor"/>
      <rect x="10" y="6"  width="6" height="11" rx="3" fill="currentColor"/>
      <rect x="24" y="6"  width="6" height="11" rx="3" fill="currentColor"/>
      <circle cx="16" cy="21" r="1.4" fill="var(--bg-pane)"/>
      <circle cx="24" cy="21" r="1.4" fill="var(--bg-pane)"/>
    </svg>
  ),
};

window.I = I;

// ── Activity — universal "in-progress" indicator ─────────────────────────
// 3 staggered pulsing dots. Used everywhere the system signals "alive / working":
// thinking, checking, running, working, syncing, pairing.
//
// Sizes (dot diameter):
//   sm: 3px  — inline inside pills/rows (workgroup row, tool call trailing)
//   md: 4px  — popovers (version, peers, pair device)
//   lg: 6px  — message slot, composer-adjacent
//   xl: 8px  — empty message slot (thinking before any token)
//
// Color: defaults to currentColor — set color: on the parent.
function Activity({ size = 'md', style }) {
  const px = ({ sm: 3, md: 4, lg: 6, xl: 8 })[size] || 4;
  const gap = ({ sm: 1.5, md: 2, lg: 3, xl: 4 })[size] || 2;
  return (
    <span
      role="status"
      aria-label="in progress"
      style={{ display: 'inline-flex', gap, alignItems: 'center', ...style }}
    >
      {[0, 1, 2].map(i => (
        <span key={i} style={{
          width: px, height: px, borderRadius: '50%',
          background: 'currentColor',
          animation: `pulse-dot 1.4s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
    </span>
  );
}
window.Activity = Activity;

// ── Tip — styled tooltip wrapper ─────────────────────────────────────────
// Usage: <Tip text="Refresh"><button …/></Tip>
// `side`: 'down' (default) | 'up' | 'l' (align tip to the left edge) | 'r' (right)
function Tip({ text, side = 'down', children, block = false, style }) {
  if (!text) return children;
  const cls = 'tip-body' + (side === 'r' ? ' tip-r' : side === 'l' ? ' tip-l' : side === 'up' ? ' tip-up' : '');
  return (
    <span className="tip" style={{ display: block ? 'flex' : 'inline-flex', width: block ? '100%' : 'auto', ...style }}>
      {children}
      <span className={cls}>{text}</span>
    </span>
  );
}
window.Tip = Tip;
