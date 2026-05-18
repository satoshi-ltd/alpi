import { forwardRef } from "react";

const ActionLink = forwardRef(function ActionLink(
  { children, danger = false, className = "", style, type, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type || "button"}
      className={`ds-alink ${danger ? "danger" : ""} ${className}`.trim()}
      style={style}
      {...rest}
    >
      {children}
    </button>
  );
});

export default ActionLink;
