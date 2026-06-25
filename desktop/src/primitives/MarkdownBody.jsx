import Markdown from "./Markdown.jsx";
import styles from "./MarkdownBody.module.css";

export default function MarkdownBody({ source, className = "", mono = false }) {
  if (!source) return null;
  const cls = [styles.body, "alpi-md", mono ? styles.mono : "", className].filter(Boolean).join(" ");
  return <Markdown as="div" source={source} className={cls} />;
}
