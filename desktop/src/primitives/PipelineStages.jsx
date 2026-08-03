import { Fragment } from "react";
import Chip from "./Chip.jsx";
import styles from "./PipelineStages.module.css";

export default function PipelineStages({ phases = [] }) {
  if (!phases.length) return null;
  return (
    <div className={styles.row}>
      {phases.map((slug, i) => (
        <Fragment key={slug}>
          <Chip size="sm">#{slug}</Chip>
          {i < phases.length - 1 && <span className={styles.arrow}>→</span>}
        </Fragment>
      ))}
    </div>
  );
}
