import { useEffect, useRef, useState } from "react";
import {
  editableSessionTitle,
  displaySessionTitle,
  SESSION_TITLE_MAX,
  setSessionTitle,
  subscribeSessionTitles,
} from "../lib/session-titles.js";
import styles from "./EditableSessionTitle.module.css";

export default function EditableSessionTitle({
  session,
  connectionId = null,
  profile,
  max = Infinity,
  className = "",
  inputClassName = "",
  disabled = false,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [revision, setRevision] = useState(0);
  const inputRef = useRef(null);
  const cancelRef = useRef(false);
  const sessionId = session?.id;
  const text = displaySessionTitle(session, { connectionId, profile, max });

  useEffect(() => subscribeSessionTitles(() => setRevision((n) => n + 1)), []);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  function beginEdit(event) {
    if (disabled || !sessionId) return;
    event?.preventDefault();
    event?.stopPropagation();
    cancelRef.current = false;
    setDraft(editableSessionTitle(session, { connectionId, profile }));
    setEditing(true);
  }

  function cancel(event) {
    event?.preventDefault();
    event?.stopPropagation();
    cancelRef.current = true;
    setEditing(false);
  }

  function commit(event) {
    event?.preventDefault();
    event?.stopPropagation();
    if (cancelRef.current) {
      cancelRef.current = false;
      setEditing(false);
      return;
    }
    setSessionTitle(connectionId, profile, sessionId, draft);
    setEditing(false);
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        className={`${styles.input} ${inputClassName}`.trim()}
        aria-label="Session title"
        value={draft}
        maxLength={SESSION_TITLE_MAX}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onDoubleClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onMouseDown={(event) => event.stopPropagation()}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === "Enter") commit(event);
          if (event.key === "Escape") cancel(event);
        }}
      />
    );
  }

  return (
    <span
      key={revision}
      className={`${styles.title} ${className}`.trim()}
      title={text}
      onDoubleClick={beginEdit}
    >
      {text}
    </span>
  );
}
