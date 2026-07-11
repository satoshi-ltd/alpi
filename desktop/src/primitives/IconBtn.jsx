// IconBtn — 28×28 icon-only button. Common chrome for header / row actions.
import { forwardRef } from "react";
import Tip from "./Tip.jsx";

const IconBtn = forwardRef(function IconBtn(
  { children, className = "", style, "aria-label": ariaLabel, tip, tipSide = "down", type, ...rest },
  ref,
) {
  const btn = (
    <button
      ref={ref}
      type={type || "button"}
      aria-label={ariaLabel ?? tip}
      className={`ds-iconbtn ${className}`.trim()}
      style={style}
      {...rest}
    >
      {children}
    </button>
  );
  return tip ? <Tip text={tip} side={tipSide}>{btn}</Tip> : btn;
});

export default IconBtn;
