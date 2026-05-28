export default function Radio({ on = false, ariaLabel }) {
  return (
    <span
      className={`ds-radio ${on ? "on" : ""}`.trim()}
      role="radio"
      aria-checked={on}
      aria-label={ariaLabel}
    >
      {on && <span className="ds-radio-dot" aria-hidden />}
    </span>
  );
}
