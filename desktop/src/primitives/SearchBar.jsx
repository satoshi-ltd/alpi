import { useEffect, useRef } from "react";
import { I, Tip } from "./index.js";
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

  const noHits = query && total === 0;
  const counter = !query ? "" : noHits ? "no hits" : `${currentIndex + 1}/${total}`;

  return (
    <div data-search-skip="1" role="search" className={styles.bar}>
      <I.Search className={styles.leadIcon} />
      <input
        ref={inputRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Find in transcript…"
        spellCheck={false}
        autoCapitalize="off"
        className={styles.input}
      />
      <span className={`mono tnum ${styles.counter} ${noHits ? styles.danger : ""}`}>
        {counter}
      </span>
      <Tip text="Previous · ⇧↵" side="r">
        <button
          type="button"
          className={`iconbtn ${styles.iconbtn}`}
          onClick={onPrev}
          disabled={total === 0}
          aria-label="Previous match"
        >
          <svg viewBox="0 0 16 16" className={`icon ${styles.chev}`}>
            <path d="M4 10l4-4 4 4" />
          </svg>
        </button>
      </Tip>
      <Tip text="Next · ↵" side="r">
        <button
          type="button"
          className={`iconbtn ${styles.iconbtn}`}
          onClick={onNext}
          disabled={total === 0}
          aria-label="Next match"
        >
          <svg viewBox="0 0 16 16" className={`icon ${styles.chev}`}>
            <path d="M4 6l4 4 4-4" />
          </svg>
        </button>
      </Tip>
      <Tip text="Close · esc" side="r">
        <button
          type="button"
          className={`iconbtn ${styles.iconbtn}`}
          onClick={onClose}
          aria-label="Close search"
        >
          <I.X />
        </button>
      </Tip>
    </div>
  );
}
