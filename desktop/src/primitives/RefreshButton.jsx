import IconBtn from "./IconBtn.jsx";
import Tip from "./Tip.jsx";
import { RefreshIcon } from "./icons.jsx";

export default function RefreshButton({
  onClick,
  tip = "Refresh thread",
  side = "r",
  ariaLabel = "Refresh",
}) {
  return (
    <Tip text={tip} side={side}>
      <IconBtn aria-label={ariaLabel} onClick={onClick}>
        <RefreshIcon />
      </IconBtn>
    </Tip>
  );
}
