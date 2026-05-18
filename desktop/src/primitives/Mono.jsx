export default function Mono({ children, tnum = false, className = "", style, as: Tag = "span" }) {
  return (
    <Tag
      className={`mono ${tnum ? "tnum" : ""} ${className}`.trim()}
      style={style}
    >
      {children}
    </Tag>
  );
}
