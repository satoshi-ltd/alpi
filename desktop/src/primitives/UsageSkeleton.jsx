import { Bone } from "./Skeleton.jsx";
import styles from "./UsageSkeleton.module.css";

const TILES = [
  { label: 34, width: 96, height: 28, lead: true },
  { label: 38, width: 56, height: 18 },
  { label: 44, width: 44, height: 18 },
  { label: 52, width: 60, height: 18 },
];

export const DAY_BARS = [39, 53, 16, 37, 92, 24, 45, 29, 13, 47, 26, 79, 50, 21];

export default function UsageSkeleton({ label = "Loading usage" }) {
  return (
    <div role="img" aria-label={label} className={styles.wrap}>
      <div className={styles.stats}>
        {TILES.map((t, i) => (
          <div key={i} data-tile className={styles.stat}>
            <div className={styles.labelSlot}>
              <Bone width={`${t.label}px`} height="8px" delay={i * 0.09} />
            </div>
            <div className={t.lead ? styles.leadSlot : styles.valueSlot}>
              <Bone width={`${t.width}px`} height={`${t.height}px`} delay={i * 0.09 + 0.045} />
            </div>
          </div>
        ))}
      </div>
      <div className={styles.track}>
        {DAY_BARS.map((h, i) => (
          <div key={i} data-bar className={styles.col}>
            <Bone width="100%" height={`${h}%`} radius="3px" className={styles.bar} delay={i * 0.09} />
          </div>
        ))}
      </div>
      <div className={styles.labels} />
      <div className={styles.foot}>
        <div className={styles.footSlot}>
          <Bone width="96px" height="8px" />
        </div>
        <div className={styles.footSlot}>
          <Bone width="150px" height="8px" delay={0.09} />
        </div>
      </div>
    </div>
  );
}
