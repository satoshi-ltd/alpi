import { forwardRef } from "react";
import Button from "./Button.jsx";

const IconBtn = forwardRef(function IconBtn({ children, tip, tipSide = "down", ...rest }, ref) {
  return (
    <Button ref={ref} variant="ghost" iconOnly tip={tip} tipSide={tipSide} {...rest}>
      {children}
    </Button>
  );
});

export default IconBtn;
