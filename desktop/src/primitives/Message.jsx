import { renderMarkdown } from "../lib/markdown.js";
import styles from "./Message.module.css";

export default function Message({
  align = "left",
  bubble = false,
  accent = null,
  tintBubble = true,
  header = null,
  body = "",
  markdown = true,
}) {
  const isRight = align === "right";
  // Resolve the accent, falling back to the theme default.
  const effectiveAccent = accent || readDefaultAccent();

  // Bubble background: tinted, neutral, or plain.
  let bubbleStyle;
  if (bubble && tintBubble) {
    bubbleStyle = {
      backgroundColor: tintFor(effectiveAccent, 0.16),
      color: "var(--color-fg)",
    };
  } else if (bubble) {
    bubbleStyle = { backgroundColor: "var(--color-hover)" };
  } else {
    bubbleStyle = undefined;
  }

  const rowClass = `${styles.row} ${isRight ? styles.right : styles.left}`;
  const bodyClass = `${styles.body} ${bubble ? styles.bubble : ""} ${
    markdown ? styles.md : styles.plain
  }`;

  return (
    <div className={rowClass}>
      <div className={styles.col}>
        {header && (
          <div className={styles.header}>
            {isRight && header.time && (
              <span className={styles.muted}>{header.time}</span>
            )}
            {isRight && header.seq != null && (
              <span className={styles.muted}>#{header.seq}</span>
            )}
            <span
              className={styles.dot}
              style={{ backgroundColor: effectiveAccent }}
            />
            <span className={styles.name}>{header.name}</span>
            {!isRight && header.seq != null && (
              <span className={styles.muted}>#{header.seq}</span>
            )}
            {!isRight && header.time && (
              <span className={styles.muted}>{header.time}</span>
            )}
          </div>
        )}
        {typeof body === "string" ? (
          markdown ? (
            <div
              className={bodyClass}
              style={bubbleStyle}
              dangerouslySetInnerHTML={{ __html: renderMarkdown(body) }}
            />
          ) : (
            <div className={bodyClass} style={bubbleStyle}>
              {body}
            </div>
          )
        ) : (
          <div className={bodyClass} style={bubbleStyle}>
            {body}
          </div>
        )}
      </div>
    </div>
  );
}

// Fallback accent if CSS variables are unavailable.
const DEFAULT_ACCENT_FALLBACK = "#c8a24e";

// Read the theme accent so tinted bubbles match the active theme.
function readDefaultAccent() {
  if (typeof window === "undefined" || !document?.documentElement) {
    return DEFAULT_ACCENT_FALLBACK;
  }
  try {
    const v = getComputedStyle(document.documentElement)
      .getPropertyValue("--color-accent")
      .trim();
    return v || DEFAULT_ACCENT_FALLBACK;
  } catch {
    return DEFAULT_ACCENT_FALLBACK;
  }
}

function tintFor(hex, alpha = 0.16) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return undefined;
  const v = parseInt(m[1], 16);
  const r = (v >> 16) & 0xff;
  const g = (v >> 8) & 0xff;
  const b = v & 0xff;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
