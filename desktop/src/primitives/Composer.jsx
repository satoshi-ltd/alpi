import { useEffect, useRef, useState } from "react";
import { SendButton } from "./index.js";
import styles from "./Composer.module.css";

export default function Composer({
  value,
  onChange,
  onSubmit,
  onCancel = null,
  disabled = false,
  canSend = true,
  placeholder = "Send a message…",
  sendTitle = "Send (⌘↵)",
  disabledTitle = "Type a message",
  leftActions = null,
  hint = null,
  embedded = false,
  mentions = [],
  accent = null,
  topBar = null,
  minHeight = null,
}) {
  const textareaRef = useRef(null);
  const [mentionState, setMentionState] = useState(null);
  const isMentionOpen = mentionState != null && mentionState.items.length > 0;

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const floor = minHeight || 0;
    const target = Math.min(220, Math.max(floor, ta.scrollHeight));
    ta.style.height = `${target}px`;
    ta.style.overflowY = ta.scrollHeight > 220 ? "auto" : "hidden";
  }, [value, minHeight]);

  function recomputeMentionContext() {
    const ta = textareaRef.current;
    if (!ta || mentions.length === 0) {
      if (mentionState) setMentionState(null);
      return;
    }
    const caret = ta.selectionStart ?? value.length;
    const ctx = getMentionContext(value, caret);
    if (!ctx) {
      if (mentionState) setMentionState(null);
      return;
    }
    const q = ctx.query.toLowerCase();
    const items = q
      ? mentions.filter(
          (m) =>
            m.id.toLowerCase().includes(q) ||
            (m.hint || "").toLowerCase().includes(q),
        )
      : mentions;
    if (items.length === 0) {
      if (mentionState) setMentionState(null);
      return;
    }
    setMentionState((prev) => ({
      startIndex: ctx.startIndex,
      query: ctx.query,
      items,
      selected: prev && prev.selected < items.length ? prev.selected : 0,
    }));
  }

  useEffect(() => {
    recomputeMentionContext();
  }, [value, mentions]);

  function selectMention(item) {
    if (item.status && item.status !== "on" && item.status !== "?") return;
    const ta = textareaRef.current;
    if (!ta || !mentionState) return;
    const caret = ta.selectionStart ?? value.length;
    const before = value.slice(0, mentionState.startIndex);
    const after = value.slice(caret);
    const inserted = `@${item.id} `;
    const next = `${before}${inserted}${after}`;
    onChange?.(next);
    setMentionState(null);
    const newCaret = before.length + inserted.length;
    requestAnimationFrame(() => {
      const cur = textareaRef.current;
      if (!cur) return;
      cur.focus();
      cur.selectionStart = cur.selectionEnd = newCaret;
    });
  }

  function handleKeyDown(e) {
    if (isMentionOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionState((s) =>
          s
            ? { ...s, selected: (s.selected + 1) % s.items.length }
            : s,
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionState((s) =>
          s
            ? {
                ...s,
                selected:
                  (s.selected - 1 + s.items.length) % s.items.length,
              }
            : s,
        );
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        selectMention(mentionState.items[mentionState.selected]);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setMentionState(null);
        return;
      }
    }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onSubmit?.();
    }
  }

  function focusOnBlankClick(e) {
    if (
      e.target.closest(
        'button, input, textarea, select, a, [role="button"], [data-no-focus]',
      )
    ) {
      return;
    }
    e.preventDefault();
    textareaRef.current?.focus();
  }

  return (
    <div
      className={`${styles.wrap} ${embedded ? styles.wrapEmbedded : ""}`}
    >
      <div
        className={styles.body}
        data-disabled={disabled || undefined}
        onMouseDown={focusOnBlankClick}
      >
        {topBar && <div className={styles.topBar}>{topBar}</div>}
        {isMentionOpen && (
          <div className={styles.mentionPopover} role="listbox">
            {mentionState.items.map((item, i) => {
              const unverified =
                item.status && item.status !== "on" && item.status !== "?";
              return (
                <button
                  type="button"
                  key={item.id}
                  role="option"
                  aria-selected={i === mentionState.selected}
                  disabled={unverified}
                  title={
                    unverified
                      ? `@${item.id} hasn't accepted your invite yet`
                      : undefined
                  }
                  className={`${styles.mentionItem} ${
                    i === mentionState.selected
                      ? styles.mentionItemActive
                      : ""
                  } ${unverified ? styles.mentionItemDisabled : ""}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    if (unverified) return;
                    selectMention(item);
                  }}
                >
                  <span
                    className={styles.mentionDot}
                    style={
                      item.accent && !unverified
                        ? { backgroundColor: item.accent }
                        : undefined
                    }
                    aria-hidden
                  />
                  <span className={styles.mentionId}>{item.id}</span>
                  {unverified && (
                    <span className={styles.mentionUnverified}>
                      pending
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
        <textarea
          ref={textareaRef}
          className={styles.input}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          onKeyDown={handleKeyDown}
          onSelect={recomputeMentionContext}
          onBlur={() => setMentionState(null)}
          rows={1}
          disabled={disabled}
        />
        <div className={styles.row}>
          {hint && <span className={styles.hint}>{hint}</span>}
          <span className={styles.spacer} />
          {leftActions}
          {onCancel ? (
            <SendButton variant="stop" canSend onClick={onCancel} title="Stop generating" />
          ) : (
            <SendButton
              canSend={canSend && !disabled}
              accent={accent}
              onClick={() => onSubmit?.()}
              title={canSend ? sendTitle : disabledTitle}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function getMentionContext(text, caret) {
  if (caret === 0) return null;
  for (let i = caret - 1; i >= 0; i--) {
    const ch = text[i];
    if (ch === "@") {
      if (i > 0 && !/\s/.test(text[i - 1])) return null;
      const query = text.slice(i + 1, caret);
      if (/\s/.test(query)) return null;
      return { startIndex: i, query };
    }
    if (/\s/.test(ch)) return null;
  }
  return null;
}
