export default function DisplayHeading({ hero = false, as: Tag = "h1", children, className = "", style }) {
  return (
    <Tag
      className={`${hero ? "display-hero" : "display"} ${className}`.trim()}
      style={{ margin: 0, ...style }}
    >
      {children}
    </Tag>
  );
}
