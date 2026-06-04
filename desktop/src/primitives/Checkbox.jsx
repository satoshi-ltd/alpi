import Icon from "./Icon.jsx";

export default function Checkbox({ on = false, ariaLabel }) {
  return (
    <span
      className={`ds-checkbox ${on ? "on" : ""}`.trim()}
      role="checkbox"
      aria-checked={on}
      aria-label={ariaLabel}
    >
      {on && <Icon name="check" size={12} strokeWidth={3} />}
    </span>
  );
}
