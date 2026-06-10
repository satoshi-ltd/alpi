import { useState } from "react";
import { fmtTok, formatUsd as usd } from "../../lib/format.js";
import styles from "./Usage.module.css";

export { fmtTok };

const PRICE_IN = 0.15 / 1e6;
const PRICE_OUT = 0.6 / 1e6;
const CHART_H = 104;
const SCALE_HEADROOM = 1.08;

function costOf(d) {
  if (d.cost != null) return d.cost;
  return (d.tokIn || 0) * PRICE_IN + (d.tokOut || 0) * PRICE_OUT;
}

function tokensOf(d) {
  return (d.tokIn || 0) + (d.tokOut || 0);
}

export default function Usage({ days = [], accent = "var(--accent)", capLine = null }) {
  const [hover, setHover] = useState(null);
  if (!days.length) return null;

  const today = days.find((d) => d.today) ?? days[days.length - 1];
  const totIn = days.reduce((s, d) => s + (d.tokIn || 0), 0);
  const totOut = days.reduce((s, d) => s + (d.tokOut || 0), 0);
  const totCost = days.reduce((s, d) => s + costOf(d), 0);
  const avg = totCost / days.length;
  const maxTok = Math.max(0, ...days.map(tokensOf));
  const scale = (maxTok || 1) * SCALE_HEADROOM;

  const capNum = typeof capLine === "number" && capLine > 0 ? capLine : null;
  const todayCost = costOf(today);
  const pctLeft =
    capNum != null ? Math.max(0, Math.round((1 - todayCost / capNum) * 100)) : null;

  return (
    <div className={styles.wrap} style={{ "--u-accent": accent }}>
      <div className={styles.stats}>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Today</div>
          <div className={`${styles.today} tnum`}>{usd(todayCost)}</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Input</div>
          <div className={`${styles.statValue} tnum`}>
            {fmtTok(today.tokIn || 0)}
            <span className={styles.unit}>tok</span>
          </div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Output</div>
          <div className={`${styles.statValue} tnum`}>
            {fmtTok(today.tokOut || 0)}
            <span className={styles.unit}>tok</span>
          </div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>{capNum != null ? "Cap / day" : "Avg / day"}</div>
          <div className={`${styles.statValue} tnum`}>
            {capNum != null ? usd(capNum) : usd(avg)}
            {capNum != null && <span className={styles.unit}>{pctLeft}% left</span>}
          </div>
        </div>
      </div>

      <div className={styles.chart}>
        <div className={styles.track}>
          {days.map((d, i) => {
            const tok = tokensOf(d);
            const totalPx = (tok / scale) * CHART_H;
            const outPx = tok > 0 ? Math.min(totalPx, ((d.tokOut || 0) / scale) * CHART_H) : 0;
            const dim = hover != null && hover !== i;
            const hasData = tok > 0 || costOf(d) > 0;
            return (
              <div
                key={d.iso}
                data-day={d.iso}
                className={styles.col}
                onMouseEnter={() => { if (hasData) setHover(i); }}
                onMouseLeave={() => setHover(null)}
              >
                {hover === i && (
                  <div className={styles.tipAnchor}>
                    <div className={`anim-pop ${styles.tip}`}>
                      <div className={styles.tipDay}>
                        {d.day}
                        {d.today && <span className={styles.tipToday}> · today</span>}
                      </div>
                      <div className={`${styles.tipCost} tnum`}>{usd(costOf(d))}</div>
                      <div className={styles.tipRow}>
                        <span className={`${styles.swatch} ${styles.swatchIn}`} />
                        in
                        <span className={`${styles.tipTok} tnum`}>{fmtTok(d.tokIn || 0)}</span>
                      </div>
                      <div className={styles.tipRow}>
                        <span className={`${styles.swatch} ${styles.swatchOut}`} />
                        out
                        <span className={`${styles.tipTok} tnum`}>{fmtTok(d.tokOut || 0)}</span>
                      </div>
                    </div>
                  </div>
                )}
                <div
                  className={`${styles.bar} ${dim ? styles.dim : ""} ${d.today ? styles.barToday : ""}`}
                  style={{ height: `${Math.max(tok > 0 ? 3 : 0, totalPx)}px` }}
                >
                  <div className={styles.barOut} style={{ height: `${outPx}px` }} />
                  <div className={styles.barIn} />
                </div>
              </div>
            );
          })}
        </div>
        <div className={styles.labels}>
          {days.map((d) => (
            <div
              key={d.iso}
              className={`${styles.dayLabel} ${d.today ? styles.dayLabelToday : ""}`}
            >
              {d.label}
            </div>
          ))}
        </div>
      </div>

      <div className={styles.foot}>
        <div className={styles.legend}>
          <span className={`${styles.swatch} ${styles.swatchIn}`} />
          input
          <span className={styles.legendSep} />
          <span className={`${styles.swatch} ${styles.swatchOut}`} />
          output
        </div>
        <div className={`${styles.totals} tnum`}>
          14-day total {usd(totCost)} · {fmtTok(totIn)} in / {fmtTok(totOut)} out
        </div>
      </div>
    </div>
  );
}
