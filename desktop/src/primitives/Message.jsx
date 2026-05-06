import { memo, useEffect, useRef, useState } from "react";
import { renderMarkdown } from "../lib/markdown.js";
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
  const [footerVisible, setFooterVisible] = useState(false);
  const hideTimerRef = useRef(null);
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

  const colClass = `${styles.col} ${footer ? styles.colFooter : ""}`;

  useEffect(
    () => () => {
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    },
    [],
  );

  function showFooterNow() {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
    setFooterVisible(true);
  }

  function hideFooterSoon() {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => {
      hideTimerRef.current = null;
      setFooterVisible(false);
    }, 180);
  }

  return (
    <div className={rowClass}>
      <div
        className={colClass}
        onMouseEnter={showFooterNow}
        onMouseLeave={hideFooterSoon}
        onFocusCapture={showFooterNow}
        onBlurCapture={(e) => {
          if (e.currentTarget.contains(e.relatedTarget)) return;
          hideFooterSoon();
        }}
      >
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
        {footer && footerVisible && (
          <div
            className={`${styles.footer} ${styles.footerVisible} ${
              isRight ? styles.footerRight : styles.footerLeft
            }`}
            onMouseEnter={showFooterNow}
            onMouseLeave={hideFooterSoon}
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
