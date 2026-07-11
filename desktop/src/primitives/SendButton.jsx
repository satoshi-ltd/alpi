import { SendIcon, StopIcon, SpinnerIcon } from "./icons.jsx";
import Tip from "./Tip.jsx";

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
  const fg = enabled || isStop ? "#fff" : "var(--ink-3)";
  const btn = (
    <button
      type="button"
      onClick={clickable ? onClick : undefined}
      disabled={isStop ? stopping : !enabled}
      aria-label={isStop ? (stopping ? "Stopping" : "Stop") : "Send"}
      style={{
        width: 30,
        height: 30,
        borderRadius: 10,
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
