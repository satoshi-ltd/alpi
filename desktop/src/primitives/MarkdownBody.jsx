import { renderMarkdown } from "../lib/markdown.js";
import styles from "./MarkdownBody.module.css";

export default function MarkdownBody({ source, className = "" }) {
  if (!source) return null;
  return (
    <div
      className={`${styles.body} alpi-md ${className}`.trim()}
      dangerouslySetInnerHTML={{ __html: renderMarkdown(source) }}
    />
  );
}
