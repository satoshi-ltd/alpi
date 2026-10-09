import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import NavRow from "../../primitives/NavRow.jsx";
import { SearchIcon } from "../../primitives/icons.jsx";
import styles from "./Settings.module.css";
import { isComposing } from "../../lib/composition.js";

export const QueryCtx = createContext("");
const SectionHitCtx = createContext(false);

export const useSettingsQuery = () => useContext(QueryCtx);
export const useSectionTitleHit = () => useContext(SectionHitCtx);
export const SectionHitProvider = SectionHitCtx.Provider;

export function settingsMatch(text, query) {
  const q = String(query ?? "").trim().toLowerCase();
  if (!q) return true;
  if (typeof text !== "string") return false;
  return text.toLowerCase().includes(q);
}

export function sectionId(title) {
  return `settings-${String(title ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
}

const SPY_OFFSET = 32;

function readSections(root) {
  if (!root) return [];
  return Array.from(root.querySelectorAll("[data-settings-section]")).map((el) => ({
    id: el.id,
    title: el.getAttribute("data-settings-section"),
    hidden: el.hidden,
  }));
}

const sameSections = (a, b) =>
  a.length === b.length && a.every((s, i) => s.id === b[i].id && s.title === b[i].title && s.hidden === b[i].hidden);

export function activeSectionFor(sections, container) {
  if (!container) return sections[0]?.id ?? null;
  const top = container.getBoundingClientRect().top;
  if (container.scrollTop + container.clientHeight >= container.scrollHeight - 2 && container.scrollTop > 0) {
    return sections[sections.length - 1]?.id ?? null;
  }
  let current = sections[0]?.id ?? null;
  for (const s of sections) {
    const el = document.getElementById(s.id);
    if (!el) continue;
    if (el.getBoundingClientRect().top - top <= SPY_OFFSET) current = s.id;
  }
  return current;
}

export default function SettingsNav({ scrollRef, children }) {
  const [query, setQuery] = useState("");
  const [sections, setSections] = useState([]);
  const [active, setActive] = useState(null);
  const contentRef = useRef(null);
  const visible = sections.filter((s) => !s.hidden);

  useLayoutEffect(() => {
    const root = contentRef.current;
    const rescan = () => setSections((prev) => {
      const next = readSections(root);
      return sameSections(prev, next) ? prev : next;
    });
    rescan();
    if (typeof MutationObserver === "undefined" || !root) return undefined;
    const mo = new MutationObserver(rescan);
    mo.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });
    return () => mo.disconnect();
  }, []);

  useEffect(() => {
    const container = scrollRef?.current;
    const shown = sections.filter((s) => !s.hidden);
    const update = () => setActive(activeSectionFor(shown, container));
    update();
    if (!container) return undefined;
    container.addEventListener("scroll", update, { passive: true });
    return () => container.removeEventListener("scroll", update);
  }, [sections, scrollRef]);

  const jump = useCallback((id) => {
    const el = id ? document.getElementById(id) : null;
    if (!el) return;
    if (typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "start", behavior: "smooth" });
    setActive(id);
  }, []);

  const q = query.trim();
  return (
    <div className={styles.navLayout}>
      <nav className={styles.rail} aria-label="Settings sections">
        <label className={styles.railSearch}>
          <SearchIcon className={styles.railSearchIcon} />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (isComposing(e)) return;
              if (e.key === "Enter") {
                e.preventDefault();
                jump(visible[0]?.id);
              } else if (e.key === "Escape" && query) {
                e.preventDefault();
                e.stopPropagation();
                setQuery("");
              }
            }}
            placeholder="Search settings"
            aria-label="Search settings"
            spellCheck={false}
            className={styles.railSearchInput}
          />
        </label>
        {visible.map((s) => (
          <NavRow
            key={s.id}
            active={active === s.id}
            aria-current={active === s.id ? "true" : undefined}
            onClick={() => jump(s.id)}
          >
            {s.title}
          </NavRow>
        ))}
      </nav>
      <QueryCtx.Provider value={q}>
        <div ref={contentRef} className={styles.navContent}>
          {children}
          {q && sections.length > 0 && visible.length === 0 ? (
            <p className={styles.navEmpty}>No settings match “{q}”</p>
          ) : null}
        </div>
      </QueryCtx.Provider>
    </div>
  );
}
