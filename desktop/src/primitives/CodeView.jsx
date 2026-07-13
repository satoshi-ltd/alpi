import { Fragment, useMemo, useRef } from "react";
import { codeLines } from "../lib/pyhighlight.js";
import styles from "./CodeView.module.css";

const BLANK_LINE = "\u200b";

export default function CodeView({ text = "", lang, editable = false, onChange, ariaLabel }) {
  return editable
    ? <CodeEditor value={text} onChange={onChange} ariaLabel={ariaLabel} />
    : <CodeRead text={text} lang={lang} />;
}

function CodeRead({ text, lang }) {
  const lines = useMemo(() => codeLines(text, lang), [text, lang]);
  return (
    <div className={styles.codeView}>
      {lines.map((toks, i) => (
        <div className={styles.codeLine} key={i}>
          <span className={styles.ln} aria-hidden>{i + 1}</span>
          <code className={styles.lc}>
            {toks.length === 0
              ? BLANK_LINE
              : toks.map((t, j) =>
                  t.type ? (
                    <span key={j} className={styles[`t_${t.type}`]}>{t.text}</span>
                  ) : (
                    <Fragment key={j}>{t.text}</Fragment>
                  ),
                )}
          </code>
        </div>
      ))}
    </div>
  );
}

function CodeEditor({ value, onChange, ariaLabel }) {
  const gutterRef = useRef(null);
  const count = (value.match(/\n/g)?.length ?? 0) + 1;
  const nums = Array.from({ length: count }, (_, i) => i + 1).join("\n");
  return (
    <div className={styles.editWrap}>
      <pre ref={gutterRef} className={styles.editGutter} aria-hidden>{nums}</pre>
      <textarea
        className={styles.editArea}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        onScroll={(e) => {
          if (gutterRef.current) gutterRef.current.scrollTop = e.currentTarget.scrollTop;
        }}
        spellCheck={false}
        aria-label={ariaLabel}
      />
    </div>
  );
}
