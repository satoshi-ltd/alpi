import { forwardRef } from "react";
import Button from "./Button.jsx";

const IconBtn = forwardRef(function IconBtn({ children, tip, tipSide = "down", size = "sm", ...rest }, ref) {
  return (
    <Button ref={ref} variant="ghost" size={size} iconOnly tip={tip} tipSide={tipSide} {...rest}>
      {children}
    </Button>
  );
});

export default IconBtn;
