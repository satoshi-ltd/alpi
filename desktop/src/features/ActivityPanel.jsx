import { Scrim, PanelShell } from "../primitives/Panels.jsx";
import { Button, Diamond, DiamondStack, Icon, IconBtn, Kbd } from "../primitives/index.js";
import { useNow } from "../hooks/useNow.js";
import { recentlyFailed, toEpochSeconds } from "../hooks/useActivity.js";
import { profileLabel } from "../lib/profile-display.js";
import { formatNextFire, relativeTime } from "../lib/time.js";
import styles from "./ActivityPanel.module.css";

function ago(seconds, now) {
  if (!seconds) return "";
  const rel = relativeTime(seconds, now);
  return rel === "now" ? "just now" : `${rel} ago`;
}

function Row({ glyph, title, sub, action = null, onClick = null, tone = null }) {
  const body = (
    <>
      <span className={styles.glyph} data-tone={tone || undefined}>{glyph}</span>
      <span className={styles.text}>
        <span className={styles.title}>{title}</span>
        {sub ? <span className={styles.sub}>{sub}</span> : null}
      </span>
    </>
  );
  return (
    <li className={styles.row}>
      {onClick ? (
        <button type="button" className={styles.rowMain} onClick={onClick}>{body}</button>
      ) : (
        <span className={styles.rowMain}>{body}</span>
      )}
      {action}
    </li>
  );
}

function Group({ label, count, children }) {
  return (
    <section className={styles.group} aria-label={label}>
      <h3 className={`eyebrow ${styles.groupLabel}`}>
        {count != null ? `${label} · ${count}` : label}
      </h3>
      <ul className={styles.list}>{children}</ul>
    </section>
  );
}

export default function ActivityPanel({
  open,
  onClose,
  activity,
  accentByProfile = {},
  onReview,
  onOpenSession,
  onOpenWorkgroup,
  onOpenProfile,
}) {
  const now = useNow();
  if (!open) return null;
  const needs = activity?.needs_you ?? [];
  const running = activity?.running ?? [];
  const scheduled = activity?.scheduled ?? [];
  const empty = needs.length === 0 && running.length === 0 && scheduled.length === 0;
  const close = (fn) => (...args) => {
    fn?.(...args);
    onClose?.();
  };

  return (
    <Scrim onClose={onClose} top={80}>
      <PanelShell width={460} maxHeight="70vh">
        <div className={styles.head}>
          <Icon name="history" />
          <span className={styles.headTitle}>Activity</span>
          <span className={styles.headKeys} aria-hidden>
            <Kbd>⌘</Kbd>
            <Kbd>J</Kbd>
          </span>
          <IconBtn tip="Close" tipSide="l" onClick={onClose}>
            <Icon name="x" />
          </IconBtn>
        </div>
        <div className={`scroll ${styles.body}`}>
          {empty ? (
            <p className={styles.empty}>Nothing running · agents at work show up here</p>
          ) : null}
          {needs.length > 0 && (
            <Group label="Needs you" count={needs.length}>
              {needs.map((item) => (
                <Row
                  key={item.request_id}
                  tone="warning"
                  glyph={<Icon name="triangle-alert" />}
                  title={`${profileLabel(item.profile ?? "")} · ${item.title || (item.kind === "clarification" ? "has a question" : "wants to run a command")}`}
                  sub={`${item.kind === "clarification" ? "question" : "approval"} · ${ago(toEpochSeconds(item.ts), now)}`}
                  action={
                    <Button size="sm" variant="primary" onClick={close(() => onReview?.(item))}>
                      Review
                    </Button>
                  }
                />
              ))}
            </Group>
          )}
          {running.length > 0 && (
            <Group label="Running" count={running.length}>
              {running.map((run) =>
                run.kind === "workgroup" ? (
                  <Row
                    key={`wg:${run.profile}/${run.workgroup_id}`}
                    tone="accent"
                    glyph={<DiamondStack color={accentByProfile[run.profile] || undefined} pulse />}
                    title={`${run.name || run.workgroup_id}${run.phase ? ` · #${run.phase}` : ""}`}
                    sub={
                      Number.isInteger(run.phases_total) && run.phases_total > 0
                        ? `phase ${Math.min(run.phases_total, (run.phases_done ?? 0) + 1)} of ${run.phases_total}`
                        : run.pipeline || "workgroup"
                    }
                    onClick={close(() => onOpenWorkgroup?.(run.profile, run.workgroup_id))}
                  />
                ) : (
                  <Row
                    key={`turn:${run.profile}/${run.session_id ?? ""}`}
                    tone="accent"
                    glyph={<Diamond color={accentByProfile[run.profile] || undefined} pulse />}
                    title={`${profileLabel(run.profile ?? "")} · ${run.title || "New session"}`}
                    sub={[
                      run.started_at ? relativeTime(toEpochSeconds(run.started_at), now) : null,
                      run.source && run.source !== "chat" ? run.source : null,
                    ].filter(Boolean).join(" · ")}
                    onClick={close(() => onOpenSession?.(run.profile, run.session_id ?? null))}
                  />
                ),
              )}
            </Group>
          )}
          {scheduled.length > 0 && (
            <Group label="Scheduled">
              {scheduled.map((job) => {
                const failed = recentlyFailed(job, now / 1000);
                return (
                  <Row
                    key={`job:${job.profile}/${job.job_id}`}
                    tone={failed ? "danger" : null}
                    glyph={<Icon name={failed ? "x" : "clock"} />}
                    title={`${profileLabel(job.profile ?? "")} · ${job.title || job.job_id}`}
                    sub={
                      failed
                        ? `failed ${ago(toEpochSeconds(job.last_run_at), now)}`
                        : job.next_fire
                          ? formatNextFire(job.next_fire, now)
                          : "not scheduled"
                    }
                    onClick={close(() => onOpenProfile?.(job.profile))}
                  />
                );
              })}
            </Group>
          )}
        </div>
      </PanelShell>
    </Scrim>
  );
}
