import { useEffect, useRef } from "react";
import Kbd from "./Kbd.jsx";
import Tooltip from "./Tooltip.jsx";
import styles from "./SearchBar.module.css";

export default function SearchBar({
  query,
  setQuery,
  total,
  currentIndex,
  onNext,
  onPrev,
  onClose,
}) {
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  function onKeyDown(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (e.shiftKey) onPrev();
      else onNext();
    }
  }

  const disabled = total === 0;
  const counter = query ? `${disabled ? 0 : currentIndex + 1}/${total}` : "";

  return (
    <div className={styles.bar} role="search">
      <input
        ref={inputRef}
        className={styles.input}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Find"
        spellCheck={false}
        autoCapitalize="off"
      />
      <span className={styles.counter}>{counter}</span>
      <Tooltip
        text={
          <>
            Previous <Kbd>⇧⌘G</Kbd>
          </>
        }
      >
        <button
          type="button"
          className={styles.btn}
          onClick={onPrev}
          disabled={disabled}
          aria-label="Previous match"
        >
          ↑
        </button>
      </Tooltip>
      <Tooltip
        text={
          <>
            Next <Kbd>⌘G</Kbd>
          </>
        }
      >
        <button
          type="button"
          className={styles.btn}
          onClick={onNext}
          disabled={disabled}
          aria-label="Next match"
        >
          ↓
        </button>
      </Tooltip>
      <Tooltip
        text={
          <>
            Close <Kbd>Esc</Kbd>
          </>
        }
      >
        <button
          type="button"
          className={styles.btn}
          onClick={onClose}
          aria-label="Close search"
        >
          ✕
        </button>
      </Tooltip>
    </div>
  );
}
