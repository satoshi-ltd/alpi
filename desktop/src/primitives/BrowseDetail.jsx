import { renderMarkdownInline } from "../lib/markdown.js";
import styles from "./BrowseDetail.module.css";

export default function BrowseDetail({ name, description, path, children }) {
  return (
    <div className={styles.wrap}>
      {name && <h3 className={styles.name}>{name}</h3>}
      {description && (
        <p
          className={styles.description}
          dangerouslySetInnerHTML={{ __html: renderMarkdownInline(description) }}
        />
      )}
      {path && <div className={styles.path}>{path}</div>}
      {children}
    </div>
  );
}
