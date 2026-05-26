import { forwardRef } from "react";

const Btn = forwardRef(function Btn(
  {
    variant = "default",
    children,
    className = "",
    style,
    as: Tag = "button",
    type,
    ...rest
  },
  ref,
) {
  const variantClass =
    variant === "primary"
      ? "ds-btn-primary"
      : variant === "ghost"
        ? "ds-btn-ghost"
        : variant === "danger"
          ? "ds-btn-danger"
          : "";
  const tagProps = Tag === "button" ? { type: type || "button" } : {};
  return (
    <Tag
      ref={ref}
      className={`ds-btn ${variantClass} ${className}`.trim()}
      style={style}
      {...tagProps}
      {...rest}
    >
      {children}
    </Tag>
  );
});

export default Btn;
