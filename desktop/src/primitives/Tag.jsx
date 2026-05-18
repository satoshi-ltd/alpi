export default function Tag({ children, outlined = false, className = "", style }) {
  return (
    <span
      className={`ds-tag ${outlined ? "ds-tag-out" : ""} ${className}`.trim()}
      style={style}
    >
      {children}
    </span>
  );
}
