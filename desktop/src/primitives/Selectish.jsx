import { forwardRef } from "react";
import { CaretIcon } from "./icons.jsx";

const Selectish = forwardRef(function Selectish(
  { leading, children, className = "", style, type, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type || "button"}
      className={`ds-selectish ${className}`.trim()}
      style={style}
      {...rest}
    >
      {leading}
      <span>{children}</span>
      <CaretIcon />
    </button>
  );
});

export default Selectish;
