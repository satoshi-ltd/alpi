import { SendIcon, StopIcon } from "./icons.jsx";

export default function SendButton({
  canSend = false,
  accent,
  variant = "send",   // "send" | "stop"
  onClick,
  disabled = false,
  ...rest
}) {
  const enabled = !disabled && canSend;
  const bg =
    variant === "stop"
      ? "var(--ink)"
      : enabled
        ? accent || "var(--accent)"
        : "var(--line)";
  const fg = enabled || variant === "stop" ? "#fff" : "var(--ink-3)";
  return (
    <button
      type="button"
      onClick={enabled || variant === "stop" ? onClick : undefined}
      disabled={!enabled && variant !== "stop"}
      aria-label={variant === "stop" ? "Stop" : "Send"}
      style={{
        width: 30,
        height: 30,
        borderRadius: 10,
        border: 0,
        background: bg,
        color: fg,
        display: "grid",
        placeItems: "center",
        cursor: enabled || variant === "stop" ? "pointer" : "default",
        transition: "background var(--dur-1), transform var(--dur-1)",
      }}
      {...rest}
    >
      {variant === "stop" ? (
        <StopIcon style={{ width: 12, height: 12 }} />
      ) : (
        <SendIcon style={{ width: 14, height: 14, strokeWidth: 2 }} />
      )}
    </button>
  );
}
