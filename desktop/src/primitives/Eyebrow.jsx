export default function Eyebrow({ children, className = "", as: Tag = "span", ...rest }) {
  return (
    <Tag className={`eyebrow ${className}`.trim()} {...rest}>
      {children}
    </Tag>
  );
}
