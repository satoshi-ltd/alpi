import { useLayoutEffect, useRef } from "react";

import Markdown from "../primitives/Markdown.jsx";
import styles from "./StreamingMarkdown.module.css";

function textNodes(root) {
  const out = [];
  const walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) out.push(n);
  return out;
}

function visibleText(root) {
  return textNodes(root).filter((node) => node.data.trim()).map((node) => node.data).join("");
}

function commonPrefix(a, b) {
  const max = Math.min(a.length, b.length);
  let i = 0;
  while (i < max && a.charCodeAt(i) === b.charCodeAt(i)) i += 1;
  return i;
}

export function markNewText(root, from, className) {
  let offset = 0;
  for (const node of textNodes(root)) {
    if (!node.data.trim()) continue;
    const start = offset;
    offset += node.data.length;
    if (offset <= from) continue;
    const target = start < from ? node.splitText(from - start) : node;
    const span = root.ownerDocument.createElement("span");
    span.className = className;
    span.dataset.chunk = "";
    target.parentNode.insertBefore(span, target);
    span.appendChild(target);
  }
}

export default function StreamingMarkdown({ source, className = "alpi-md" }) {
  const ref = useRef(null);
  const seenRef = useRef("");
  useLayoutEffect(() => {
    const root = ref.current;
    if (!root) return;
    const text = visibleText(root);
    const from = commonPrefix(seenRef.current, text);
    seenRef.current = text;
    if (text.length > from) markNewText(root, from, styles.chunk);
  }, [source]);
  return (
    <div ref={ref}>
      <Markdown as="div" source={source} className={className} />
    </div>
  );
}
