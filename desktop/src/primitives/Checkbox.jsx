export default function Checkbox({ on = false, ariaLabel }) {
  return (
    <span
      className={`ds-checkbox ${on ? "on" : ""}`.trim()}
      role="checkbox"
      aria-checked={on}
      aria-label={ariaLabel}
    >
      {on && (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M20 6 9 17l-5-5" />
        </svg>
      )}
    </span>
  );
}
