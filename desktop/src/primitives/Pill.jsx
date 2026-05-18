export default function Pill({ state, children, className = "", style }) {
  const stateClass =
    state === "on"
      ? "is-on"
      : state === "err"
        ? "is-err"
        : state === "warn"
          ? "is-warn"
          : state === "off"
            ? "is-off"
            : "";
  return (
    <span className={`ds-pill ${stateClass} ${className}`.trim()} style={style}>
      {children}
    </span>
  );
}
