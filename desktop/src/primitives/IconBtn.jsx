// IconBtn — 28×28 icon-only button. Common chrome for header / row actions.
import { forwardRef } from "react";

const IconBtn = forwardRef(function IconBtn(
  { children, className = "", style, "aria-label": ariaLabel, type, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type || "button"}
      aria-label={ariaLabel}
      className={`ds-iconbtn ${className}`.trim()}
      style={style}
      {...rest}
    >
      {children}
    </button>
  );
});

export default IconBtn;
