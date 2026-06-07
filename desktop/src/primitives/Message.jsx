import { memo } from "react";
import Markdown from "./Markdown.jsx";
import styles from "./Message.module.css";

function MessageImpl({
  align = "left",
  bubble = false,
  accent = null,
  tintBubble = true,
  header = null,
  body = "",
  markdown = true,
  footer = null,
}) {
  const isRight = align === "right";
  const effectiveAccent = accent || readDefaultAccent();

  let bubbleStyle;
  if (bubble && tintBubble) {
    bubbleStyle = {
      backgroundColor: tintFor(effectiveAccent, 0.16),
      color: "var(--ink)",
    };
  } else if (bubble) {
    bubbleStyle = { backgroundColor: "var(--hover)" };
  } else {
    bubbleStyle = undefined;
  }

  const rowClass = `${styles.row} ${isRight ? styles.right : styles.left}`;
  const bodyClass = `${styles.body} ${bubble ? styles.bubble : ""} ${
    markdown ? styles.md : styles.plain
  }`;
  const colClass = `${styles.col} ${footer ? styles.colFooter : ""}`;

  return (
    <div className={rowClass}>
      <div className={colClass}>
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
              style={{ color: effectiveAccent }}
              aria-hidden
            >
              ◆
            </span>
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
            <Markdown
              as="div"
              source={body}
              className={`${bodyClass} alpi-md`}
              style={bubbleStyle}
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
        {footer && (
          <div
            className={`${styles.footer} ${
              isRight ? styles.footerRight : styles.footerLeft
            }`}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

const Message = memo(MessageImpl);
export default Message;

const DEFAULT_ACCENT_FALLBACK = "#b8954a";

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
