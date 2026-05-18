import AlpiSilhouette from "./AlpiSilhouette.jsx";
import Diamond from "./Diamond.jsx";
import Mono from "./Mono.jsx";
import { relativeTime } from "../lib/time.js";
import styles from "./NewChatHero.module.css";

export default function NewChatHero({
  profiles = [],
  recents = [],
  onOpenRecent,
  accent,
  children,
}) {
  const profileBy = (name) => profiles.find((p) => p.name === name);
  return (
    <div className={styles.root}>
      <div className={styles.body}>
        <AlpiSilhouette
          color={accent || "var(--accent)"}
          className={styles.silhouette}
        />
        <div className={styles.composer}>{children}</div>
        {recents.length > 0 && (
          <section className={styles.recents}>
            <header className={styles.recentsHeader}>
              <span className={`eyebrow ${styles.recentsTitle}`}>Recents</span>
              <span className={styles.recentsCount}>
                {recents.length} session{recents.length === 1 ? "" : "s"}
              </span>
            </header>
            <ul className={styles.recentsList}>
              {recents.map((s) => {
                const p = profileBy(s.profile);
                const accent = p?.accent || "var(--ink-3)";
                return (
                  <li key={`${s.profile}/${s.id}`}>
                    <button
                      type="button"
                      className={styles.recentRow}
                      onClick={() => onOpenRecent?.(s.profile, s.id)}
                    >
                      <Diamond color={accent} size={9} />
                      <Mono className={styles.recentHandle}>@{s.profile}</Mono>
                      <span className={styles.recentText}>{s.first_user}</span>
                      <span className={styles.recentTime}>
                        {relativeTime(s.updated_at || s.mtime)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
