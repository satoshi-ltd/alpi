import { Fragment } from "react";
import Eyebrow from "../primitives/Eyebrow.jsx";
import { inlineSegments, parseNotificationBody } from "../../../common/notificationBody.mjs";
import styles from "./NotificationBody.module.css";

function Inline({ text }) {
  return inlineSegments(text).map((s, i) => {
    if (s.t === "bold") return <strong key={i} className={styles.bold}>{s.v}</strong>;
    if (s.t === "italic") return <em key={i} className={styles.italic}>{s.v}</em>;
    if (s.t === "code") return <code key={i} className={styles.code}>{s.v}</code>;
    return <Fragment key={i}>{s.v}</Fragment>;
  });
}

function Block({ b }) {
  if (b.kind === "heading") return <div className={styles.heading}><Inline text={b.text} /></div>;
  if (b.kind === "label") return <Eyebrow as="div" className={styles.label}>{b.label}</Eyebrow>;
  if (b.kind === "labelBody") {
    return (
      <div className={styles.labelBlock}>
        <Eyebrow as="div" className={styles.label}>{b.label}</Eyebrow>
        <p className={styles.para}><Inline text={b.body} /></p>
      </div>
    );
  }
  if (b.kind === "quote") return <p className={styles.quote}><Inline text={b.text} /></p>;
  if (b.kind === "table") {
    return (
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>{b.headers.map((h, j) => <th key={j}><Inline text={h} /></th>)}</tr>
          </thead>
          <tbody>
            {b.rows.map((r, ri) => (
              <tr key={ri}>{r.map((c, ci) => <td key={ci}><Inline text={c} /></td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (b.kind === "code") return <pre className={styles.codeblock}><code>{b.text}</code></pre>;
  if (b.kind === "list") {
    const Tag = b.ordered ? "ol" : "ul";
    return (
      <Tag className={styles.list}>
        {b.items.map((it, j) => (
          <li key={j} className={styles.item}>
            <span className={styles.marker} aria-hidden="true">{it.marker}</span>
            <span className={styles.itemText}><Inline text={it.text} /></span>
          </li>
        ))}
      </Tag>
    );
  }
  return <p className={styles.para}><Inline text={b.text} /></p>;
}

export default function NotificationBody({ body, lead = false, className = "" }) {
  let blocks = parseNotificationBody(body);
  if (!blocks.length) return null;
  let leadText = null;
  if (lead && blocks[0].kind === "p") {
    leadText = blocks[0].text;
    blocks = blocks.slice(1);
  }
  return (
    <div className={`${styles.body} ${className}`.trim()}>
      {leadText != null ? <div className={styles.lead}><Inline text={leadText} /></div> : null}
      {blocks.map((b, i) => <Block key={i} b={b} />)}
    </div>
  );
}
