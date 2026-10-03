import { Icon, Mono } from "./index.js";
import styles from "./StepLadder.module.css";

export default function StepLadder({ steps }) {
  return (
    <ol className={styles.ladder}>
      {steps.map(({ id, state, label, detail }) => (
        <li key={id} className={styles.step} data-state={state}>
          <span className={styles.mark} aria-hidden="true">
            {state === "done" ? <Icon name="check" size={12} /> : state === "fail" ? <Icon name="x" size={12} /> : <span className={styles.dot} />}
          </span>
          <span className={styles.label}>{label}</span>
          {detail ? <Mono className={styles.detail}>{detail}</Mono> : null}
        </li>
      ))}
    </ol>
  );
}

export function ladderSteps(order, current, failedAt, labelFor, detailFor = () => null) {
  const index = order.indexOf(failedAt ?? current);
  return order.map((id, i) => ({
    id,
    label: labelFor(id),
    detail: detailFor(id),
    state: failedAt
      ? i < index ? "done" : i === index ? "fail" : "todo"
      : current === "done" ? "done" : i < index ? "done" : i === index ? "now" : "todo",
  }));
}
