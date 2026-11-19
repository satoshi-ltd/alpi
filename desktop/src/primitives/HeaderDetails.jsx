import { Fold, MeterChip, Mono, Tip } from "./index.js";
import { HeaderDetail } from "./ChatHeader.jsx";
import { modelLabel, modelProvider } from "../lib/modelLabel.js";
import { profileLabel } from "../lib/profile-display.js";
import styles from "./HeaderDetails.module.css";

function fmtCount(n) {
  if (!n) return "0";
  if (n < 1000) return `${n}`;
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}K`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

function fmtCost(n) {
  if (n == null || n <= 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

export function profileBudget(profile) {
  const cap = profile?.budget_daily_usd;
  if (cap == null || cap <= 0) return null;
  return { used: profile?.budget_used_usd ?? 0, cap };
}

export function ProfileDetails({ model, contextWindow = 0, ctxTokens = 0, budget = null, accent }) {
  const ctxPct = contextWindow > 0 ? Math.min(1, ctxTokens / contextWindow) : 0;
  return (
    <>
      {model && (
        <HeaderDetail label="Model">
          <span className={styles.clip} title={modelLabel(model)}><Mono className={styles.ink2}>{modelLabel(model)}</Mono></span>
        </HeaderDetail>
      )}
      {modelProvider(model) && (
        <HeaderDetail label="Provider">
          <span className={styles.clip} title={modelProvider(model)}><Mono className={styles.ink2}>{modelProvider(model)}</Mono></span>
        </HeaderDetail>
      )}
      {contextWindow > 0 && (
        <HeaderDetail label="Context">
          <MeterChip
            value={
              <>
                {fmtCount(ctxTokens)}
                <span className={styles.ink3}>/{fmtCount(contextWindow)}</span>
              </>
            }
            pct={ctxPct}
            color={accent}
            tip="Context window"
          />
        </HeaderDetail>
      )}
      {budget && (
        <HeaderDetail label="Cost today">
          <MeterChip
            value={
              <>
                {fmtCost(budget.used)}
                <span className={styles.ink3}>/${budget.cap.toFixed(2)}</span>
              </>
            }
            pct={Math.min(1, budget.used / budget.cap)}
            color={accent}
            tip="Daily budget"
          />
        </HeaderDetail>
      )}
    </>
  );
}

export function WorkgroupDetails({ hubName, hubShape, hubBio = "", memberCount = 0, status = null, budget = null, accent }) {
  const bio = (hubBio || "").trim();
  const mark = <Fold shape={hubShape} color={accent} />;
  return (
    <>
      <HeaderDetail label="Hub">
        <span className={`row row-gap ${styles.hubRow}`}>
          {bio ? <Tip text={bio} side="l">{mark}</Tip> : mark}
          <span className={styles.ink2}>{`@${profileLabel(hubName)}`}</span>
        </span>
      </HeaderDetail>
      <HeaderDetail label="Members">
        <span className={`tnum ${styles.ink2}`}>{memberCount}</span>
      </HeaderDetail>
      {status && (
        <HeaderDetail label="Status">
          <span className={styles.clip} title={status}><span className={styles.ink2} data-status="">{status}</span></span>
        </HeaderDetail>
      )}
      {budget && budget.cap > 0 && (
        <HeaderDetail label="Budget">
          <MeterChip
            value={
              <>
                ${budget.used.toFixed(2)}
                <span className={styles.ink3}>/${budget.cap.toFixed(2)}</span>
              </>
            }
            pct={Math.min(1, budget.used / budget.cap)}
            color={accent}
            tip={`Workgroup budget — spent $${budget.used.toFixed(2)} of $${budget.cap.toFixed(2)} cap`}
          />
        </HeaderDetail>
      )}
    </>
  );
}
