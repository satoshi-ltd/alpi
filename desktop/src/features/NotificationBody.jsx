import { Fragment } from "react";
import Eyebrow from "../primitives/Eyebrow.jsx";
import Icon from "../primitives/Icon.jsx";
import { errorParts, failedTitle, inlineSegments, parseNotificationBody } from "../../../common/notificationBody.mjs";
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
      <Tag className={b.items.every((it) => it.entry) ? styles.entries : styles.list}>
        {b.items.map((it, j) => it.entry ? (
          <li key={j} className={styles.entry}>
            <span className={styles.entryHead}>
              <span className={styles.entryName}>{it.entry.name}</span>
              {it.entry.meta ? <span className={styles.entryMeta}>{it.entry.meta}</span> : null}
            </span>
            {it.entry.text ? <span className={styles.entryText}><Inline text={it.entry.text} /></span> : null}
          </li>
        ) : (
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

export function ErrorCard({ title, body, actions = null }) {
  const { lead, failed } = failedTitle(title);
  const { facts, details, rest } = errorParts(parseNotificationBody(body));
  return (
    <section className={styles.errorCard} aria-label={title || "Failure"}>
      <h2 className={styles.errorHead}>
        <Icon name="triangle-alert" size={14} color="var(--c-danger)" />
        <span className={styles.errorTitle}>
          {lead ? lead : <span className={styles.failed}>Failed</span>}
          {failed ? <> <span className={styles.failed}>failed</span></> : null}
        </span>
      </h2>
      {facts.length ? (
        <dl className={styles.facts}>
          {facts.map((f, i) => (
            <div key={i} className={styles.fact}>
              <dt className={styles.factLabel}>{f.label}</dt>
              <dd className={styles.factValue}><Inline text={f.body} /></dd>
            </div>
          ))}
        </dl>
      ) : null}
      {rest.length ? <div className={styles.body}>{rest.map((b, i) => <Block key={i} b={b} />)}</div> : null}
      {details.length ? (
        <details className={styles.details}>
          <summary className={styles.detailsSummary}>Details</summary>
          {details.map((b, i) => <pre key={i} className={styles.detailsTrace}><code>{b.text}</code></pre>)}
        </details>
      ) : null}
      {actions ? <div className={styles.errorActions}>{actions}</div> : null}
    </section>
  );
}
