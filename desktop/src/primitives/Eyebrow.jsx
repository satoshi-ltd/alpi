// Eyebrow — mono uppercase section / category label. 10 px / 500 / 0.06em.
export default function Eyebrow({ children, className = "", style, as: Tag = "span" }) {
  return (
    <Tag className={`eyebrow ${className}`.trim()} style={style}>
      {children}
    </Tag>
  );
}
