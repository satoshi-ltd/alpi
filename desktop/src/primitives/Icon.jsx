import styles from "./Icon.module.css";

const SIZES = { sm: 12, md: 14, lg: 18, xl: 24 };

const PATHS = {
  search: { vb: "0 0 16 16", body: <><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5l3 3" /></> },
  plus: { vb: "0 0 16 16", body: <path d="M8 3v10M3 8h10" /> },
  arrow: { vb: "0 0 16 16", body: <path d="M8 13V3M4 7l4-4 4 4" /> },
  "arrow-left": { vb: "0 0 16 16", body: <path d="M3 8h10M7 4L3 8l4 4" /> },
  "arrow-right": { vb: "0 0 16 16", body: <path d="M3 8h10M9 4l4 4-4 4" /> },
  refresh: { vb: "0 0 16 16", body: <path d="M3 7a5 5 0 019.2-2.5M13 9a5 5 0 01-9.2 2.5M11 2v3h-3M5 14v-3h3" /> },
  sidebar: { vb: "0 0 16 16", body: <><rect x="2" y="3" width="12" height="10" rx="2" /><path d="M6 3v10" /></> },
  "sidebar-open": { vb: "0 0 24 24", body: <><rect width="18" height="18" x="3" y="3" rx="2" /><path d="M15 3v18" /><path d="m8 9 3 3-3 3" /></>, sw: 2 },
  "sidebar-close": { vb: "0 0 24 24", body: <><rect width="18" height="18" x="3" y="3" rx="2" /><path d="M15 3v18" /><path d="m10 15-3-3 3-3" /></>, sw: 2 },
  gear: { vb: "0 0 16 16", body: <><circle cx="8" cy="8" r="2.2" /><path d="M8 2.2v1.6M8 12.2v1.6M2.2 8h1.6M12.2 8h1.6M4 4l1.1 1.1M10.9 10.9L12 12M4 12l1.1-1.1M10.9 5.1L12 4" /></> },
  check: { vb: "0 0 16 16", body: <path d="M3 8l3.5 3.5L13 5" /> },
  x: { vb: "0 0 16 16", body: <path d="M4 4l8 8M12 4l-8 8" /> },
  pause: { vb: "0 0 16 16", body: <><rect x="4" y="3.5" width="2.5" height="9" rx="0.5" /><rect x="9.5" y="3.5" width="2.5" height="9" rx="0.5" /></> },
  play: { vb: "0 0 16 16", body: <path d="M5 3l8 5-8 5z" fill="currentColor" stroke="none" /> },
  copy: { vb: "0 0 16 16", body: <><rect x="5" y="5" width="8" height="8" rx="1.5" /><path d="M3 11V4a1 1 0 011-1h7" /></> },
  help: { vb: "0 0 16 16", body: <><circle cx="8" cy="8" r="6" /><path d="M6.4 6.2a1.7 1.7 0 113.2.6c0 1-.9 1.2-1.6 2v.4" /><circle cx="8" cy="11.5" r=".5" fill="currentColor" stroke="none" /></> },
  cpu: { vb: "0 0 16 16", body: <><rect x="3.5" y="3.5" width="9" height="9" rx="1.5" /><rect x="6" y="6" width="4" height="4" rx=".5" /><path d="M2 6h1.5M2 10h1.5M12.5 6H14M12.5 10H14M6 2v1.5M10 2v1.5M6 12.5V14M10 12.5V14" /></> },
  wifi: { vb: "0 0 16 16", body: <><path d="M2 5.5a9 9 0 0112 0M4 8a6 6 0 018 0M6 10.5a3 3 0 014 0" /><circle cx="8" cy="13" r=".7" fill="currentColor" stroke="none" /></> },
  globe: { vb: "0 0 16 16", body: <><circle cx="8" cy="8" r="6" /><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2C6 4 6 12 8 14" /></> },
  sun: { vb: "0 0 16 16", body: <><circle cx="8" cy="8" r="3" /><path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.3 3.3l1 1M11.7 11.7l1 1M3.3 12.7l1-1M11.7 4.3l1-1" /></> },
  moon: { vb: "0 0 16 16", body: <path d="M12.5 9.5A5 5 0 016.5 3.5a5.5 5.5 0 106 6z" /> },
  auto: { vb: "0 0 16 16", body: <><circle cx="8" cy="8" r="5.5" /><path d="M8 2.5v11" /><path d="M8 2.5a5.5 5.5 0 010 11z" fill="currentColor" stroke="none" /></> },
  trash: { vb: "0 0 16 16", body: <path d="M3 4h10M6 4V2.5h4V4M4.5 4l.6 9a1 1 0 001 1h3.8a1 1 0 001-1l.6-9" /> },
  "chev-down": { vb: "0 0 16 16", body: <path d="M4 6l4 4 4-4" /> },
  "chev-right": { vb: "0 0 16 16", body: <path d="M6 4l4 4-4 4" /> },
  send: { vb: "0 0 16 16", body: <path d="M8 13V3M4 7l4-4 4 4" /> },
  dollar: { vb: "0 0 16 16", body: <path d="M8 2v12M11 5.5C11 4 9.5 3 8 3s-3 .8-3 2.2c0 2.8 6 1.8 6 4.6 0 1.5-1.5 2.2-3 2.2s-3-1-3-2.5" /> },
  spark: { vb: "0 0 16 16", body: <path d="M8 2v3M8 11v3M2 8h3M11 8h3M4.5 4.5l1.7 1.7M9.8 9.8l1.7 1.7M4.5 11.5l1.7-1.7M9.8 6.2l1.7-1.7" /> },
  tag: { vb: "0 0 16 16", body: <><path d="M2.5 8.5l6 6 6-6-6-6h-6z" /><circle cx="5.5" cy="5.5" r=".8" /></> },
  folder: { vb: "0 0 16 16", body: <path d="M2 4.5A1.5 1.5 0 013.5 3H6l1.5 1.5h5A1.5 1.5 0 0114 6v6a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 012 12V4.5z" /> },
  eye: { vb: "0 0 16 16", body: <><path d="M1.5 8C3 5 5.3 3.5 8 3.5S13 5 14.5 8C13 11 10.7 12.5 8 12.5S3 11 1.5 8z" /><circle cx="8" cy="8" r="2" /></> },
  mute: { vb: "0 0 16 16", body: <><path d="M3 5h2.5L9 2.5v11L5.5 11H3z" stroke="currentColor" strokeWidth="1.5" fill="none" /><path d="M11 5l4 6M15 5l-4 6" stroke="currentColor" strokeWidth="1.5" /></> },
  archive: { vb: "0 0 16 16", body: <><rect x="2" y="3.5" width="12" height="3" rx=".5" /><path d="M3 6.5v6a1 1 0 001 1h8a1 1 0 001-1v-6M6.5 9h3" /></> },
  bell: { vb: "0 0 16 16", body: <><path d="M4 11V7a4 4 0 018 0v4l1 1.5H3z" /><path d="M6.5 13a1.5 1.5 0 003 0" /></> },
  skip: { vb: "0 0 16 16", body: <><circle cx="8" cy="8" r="6" /><path d="M4 12L12 4" /></> },
  stop: { vb: "0 0 16 16", body: <rect x="4" y="4" width="8" height="8" rx="1.5" fill="currentColor" stroke="none" /> },
  volume: { vb: "0 0 16 16", body: <><path d="M3 6v4h2l3 2.5V3.5L5 6H3z" /><path d="M10.5 5.5a3 3 0 010 5M12.5 3.5a5.5 5.5 0 010 9" /></> },
  edit: { vb: "0 0 16 16", body: <path d="M11 2.5l2.5 2.5L6 12.5H3.5V10z" /> },
  caret: { vb: "0 0 16 16", body: <path d="M4 6l4 4 4-4" /> },
  back: { vb: "0 0 24 24", body: <><path d="m12 19-7-7 7-7" /><path d="M19 12H5" /></>, sw: 2 },
  question: { vb: "0 0 24 24", body: <><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><path d="M12 17h.01" /></>, sw: 2 },
  undo: { vb: "0 0 24 24", body: <><path d="M9 14 4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11" /></>, sw: 2 },
  alpi: { vb: "0 0 24 24", body: <path d="M12 3 21 12 12 21 3 12Z" />, sw: 0, fill: "currentColor" },
  "local-connection": { vb: "0 0 24 24", body: <><path d="M12 20v2" /><path d="M12 2v2" /><path d="M17 20v2" /><path d="M17 2v2" /><path d="M2 12h2" /><path d="M2 17h2" /><path d="M2 7h2" /><path d="M20 12h2" /><path d="M20 17h2" /><path d="M20 7h2" /><path d="M7 20v2" /><path d="M7 2v2" /><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="8" y="8" width="8" height="8" rx="1" /></>, sw: 2 },
  "remote-connection": { vb: "0 0 24 24", body: <><rect width="20" height="8" x="2" y="14" rx="2" /><path d="M6.01 18H6" /><path d="M10.01 18H10" /><path d="M15 10v4" /><path d="M17.84 7.17a4 4 0 0 0-5.66 0" /><path d="M20.66 4.34a8 8 0 0 0-11.31 0" /></>, sw: 2 },
};

export default function Icon({
  name,
  size = "md",
  color = null,
  className = "",
  style = null,
  ...rest
}) {
  const def = PATHS[name];
  if (!def) {
    if (typeof console !== "undefined") console.warn(`<Icon name="${name}"/> not in map`);
    return null;
  }
  const px = typeof size === "number" ? size : (SIZES[size] || SIZES.md);
  const fill = def.fill || "none";
  const stroke = def.fill === "currentColor" ? "none" : "currentColor";
  const sw = def.sw == null ? 1.5 : def.sw;
  return (
    <svg
      viewBox={def.vb}
      width={px}
      height={px}
      fill={fill}
      stroke={stroke}
      strokeWidth={sw || undefined}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`${styles.icon} ds-icon ${className}`.trim()}
      style={{ color: color ?? undefined, ...style }}
      aria-hidden="true"
      {...rest}
    >
      {def.body}
    </svg>
  );
}
