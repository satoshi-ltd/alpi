import { Fragment } from "react";
import Fold from "./Fold.jsx";
import Skeleton from "./Skeleton.jsx";
import Tip from "./Tip.jsx";
import styles from "./PipelineStages.module.css";

const STATE_WORD = { current: "running", skipped: "skipped", blocked: "blocked" };

function Mark({ name, profileOf, pulse }) {
  if (!name) return null;
  const profile = profileOf?.(name);
  if (!profile) return <Fold fold="diamond" size={12} unfolded />;
  return <Fold fold={profile.fold} color={profile.accent} size={12} pulse={pulse} />;
}

function ChipBody({ chip, profileOf }) {
  const working = chip.state === "current";
  return (
    <>
      <Mark name={chip.owner} profileOf={profileOf} pulse={working && !chip.assignee} />
      <span className={styles.slug}>#{chip.slug}</span>
      {chip.assignee && (
        <span className={styles.handoff}>
          <span className={styles.arrow} aria-hidden>→</span>
          <Mark name={chip.assignee} profileOf={profileOf} pulse={working} />
          <span className={styles.assignee}>@{chip.assignee}</span>
        </span>
      )}
    </>
  );
}

function label(chip) {
  const who = [chip.owner && `@${chip.owner}`, chip.assignee && `→ @${chip.assignee}`].filter(Boolean).join(" ");
  const word = STATE_WORD[chip.state] ?? chip.state;
  return [`#${chip.slug}`, who, word].filter(Boolean).join(" · ");
}

export default function PipelineStages({ phases = [], chips = null, profileOf = null, onJump = null, canJump = null, detail = null }) {
  const items = chips ?? phases.map((slug) => ({ slug, owner: null, state: "pending" }));
  if (!items.length) return null;
  return (
    <div className={styles.row}>
      {items.map((chip, i) => {
        const jumpable = !!onJump && (canJump ? canJump(chip) : true);
        const body = <ChipBody chip={chip} profileOf={profileOf} />;
        const card = detail?.(chip, jumpable);
        const node = jumpable ? (
          <button
            type="button"
            className={`${styles.chip} ${styles.button}`}
            data-phase={chip.slug}
            data-state={chip.state}
            aria-label={`Jump to ${label(chip)}`}
            onClick={() => onJump(chip)}
          >
            {body}
          </button>
        ) : (
          <span
            className={styles.chip}
            data-phase={chip.slug}
            data-state={chip.state}
            aria-disabled={onJump ? "true" : undefined}
            tabIndex={card ? 0 : undefined}
            aria-label={card ? label(chip) : undefined}
            title={card ? undefined : label(chip)}
          >
            {body}
          </span>
        );
        return (
          <Fragment key={chip.slug}>
            {card ? <Tip text={card} side={i < items.length / 2 ? "l" : "r"} wide>{node}</Tip> : node}
            {i < items.length - 1 && <span className={styles.arrow} aria-hidden>→</span>}
          </Fragment>
        );
      })}
    </div>
  );
}

const GHOST_WIDTHS = [62, 70, 66, 70, 74, 64];

export function PipelinePlaceholder({ count, label }) {
  const n = Math.min(Math.max(Number.isInteger(count) ? count : 3, 1), GHOST_WIDTHS.length);
  return (
    <div className={styles.row} role="status" aria-label={label}>
      {Array.from({ length: n }, (_, i) => (
        <Fragment key={i}>
          <span className={styles.ghost} data-phase-placeholder="" aria-hidden>
            <Skeleton width={`${GHOST_WIDTHS[i]}px`} height="22px" radius="var(--r-tag)" delay={0} />
          </span>
          {i < n - 1 && <span className={styles.arrow} aria-hidden>→</span>}
        </Fragment>
      ))}
    </div>
  );
}
