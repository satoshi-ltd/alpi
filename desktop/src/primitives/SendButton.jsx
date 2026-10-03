import { SendIcon, StopIcon, SpinnerIcon } from "./icons.jsx";
import Tip from "./Tip.jsx";
import { contrastRatio } from "../../../common/crease.mjs";
import { BRAND_INK, isHexColour } from "../../../common/folds.mjs";

const LIGHT_FG = "#ffffff";

export function foregroundOn(fill) {
  if (!isHexColour(fill)) return "var(--bg-pane)";
  return contrastRatio(LIGHT_FG, fill) >= contrastRatio(BRAND_INK.light, fill) ? LIGHT_FG : BRAND_INK.light;
}

export default function SendButton({
  canSend = false,
  accent,
  variant = "send",   // "send" | "stop"
  onClick,
  disabled = false,
  stopping = false,
  title,
  ...rest
}) {
  const enabled = !disabled && canSend;
  const isStop = variant === "stop";
  const clickable = isStop ? !stopping : enabled;
  const bg = isStop
    ? "var(--ink)"
    : enabled
      ? accent || "var(--accent)"
      : "var(--line)";
  const fg = enabled || isStop ? foregroundOn(bg) : "var(--ink-3)";
  const btn = (
    <button
      type="button"
      onClick={clickable ? onClick : undefined}
      disabled={isStop ? stopping : !enabled}
      aria-label={isStop ? (stopping ? "Stopping" : "Stop") : "Send"}
      style={{
        width: "var(--ctrl-md)",
        height: "var(--ctrl-md)",
        borderRadius: "var(--r-xs)",
        border: 0,
        background: bg,
        color: fg,
        opacity: stopping ? 0.65 : 1,
        display: "grid",
        placeItems: "center",
        cursor: clickable ? "pointer" : "default",
        transition: "background var(--dur-1), transform var(--dur-1), opacity var(--dur-1)",
      }}
      {...rest}
    >
      {isStop ? (
        stopping ? (
          <SpinnerIcon style={{ width: 14, height: 14 }} />
        ) : (
          <StopIcon style={{ width: 12, height: 12 }} />
        )
      ) : (
        <SendIcon style={{ width: 14, height: 14, strokeWidth: 2 }} />
      )}
    </button>
  );
  return title ? <Tip text={title} side="up">{btn}</Tip> : btn;
}
