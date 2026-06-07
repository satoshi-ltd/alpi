import Markdown from "./Markdown.jsx";
import styles from "./MarkdownBody.module.css";

export default function MarkdownBody({ source, className = "" }) {
  if (!source) return null;
  return (
    <Markdown as="div" source={source} className={`${styles.body} alpi-md ${className}`.trim()} />
  );
}
