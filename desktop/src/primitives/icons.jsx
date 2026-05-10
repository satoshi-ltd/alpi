import Icon from "./Icon.jsx";
import iconStyles from "./Icon.module.css";

export function BackIcon({ size = 16, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m12 19-7-7 7-7" />
        <path d="M19 12H5" />
      </svg>
    </Icon>
  );
}

export function SidebarOpenIcon({ size = 16, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="18" height="18" x="3" y="3" rx="2" />
        <path d="M15 3v18" />
        <path d="m8 9 3 3-3 3" />
      </svg>
    </Icon>
  );
}

export function SidebarCloseIcon({ size = 16, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="18" height="18" x="3" y="3" rx="2" />
        <path d="M15 3v18" />
        <path d="m10 15-3-3 3-3" />
      </svg>
    </Icon>
  );
}

export function PlusIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 14 14" fill="none">
        <path
          d="M7 2.5v9M2.5 7h9"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
      </svg>
    </Icon>
  );
}

export function CopyIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
        <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
      </svg>
    </Icon>
  );
}

export function UndoIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 14 4 9l5-5" />
        <path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11" />
      </svg>
    </Icon>
  );
}

export function QuestionIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <path d="M12 17h.01" />
      </svg>
    </Icon>
  );
}

export function CheckIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className} color="var(--color-success, #30d158)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 6 9 17l-5-5" />
      </svg>
    </Icon>
  );
}

export function RefreshIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
        <path d="M3 3v5h5" />
        <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
        <path d="M16 16h5v5" />
      </svg>
    </Icon>
  );
}

export function AlpiIcon({ size = 12, className = "", color = null }) {
  return (
    <Icon size={size} className={className} color={color}>
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 3 21 12 12 21 3 12Z" />
      </svg>
    </Icon>
  );
}

export function SendIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m5 12 7-7 7 7" />
        <path d="M12 19V5" />
      </svg>
    </Icon>
  );
}

export function StopIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="18" height="18" x="3" y="3" rx="2" />
      </svg>
    </Icon>
  );
}

export function CaretIcon({ size = 10, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m6 9 6 6 6-6" />
      </svg>
    </Icon>
  );
}

export function LocalConnectionIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 20v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M12 2v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M17 20v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M17 2v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M2 12h2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M2 17h2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M2 7h2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M20 12h2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M20 17h2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M20 7h2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M7 20v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M7 2v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <rect x="4" y="4" width="16" height="16" rx="2" stroke="currentColor" strokeWidth="2" />
        <rect x="8" y="8" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="2" />
      </svg>
    </Icon>
  );
}

export function RemoteConnectionIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none">
        <rect width="20" height="8" x="2" y="14" rx="2" stroke="currentColor" strokeWidth="2" />
        <path d="M6.01 18H6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M10.01 18H10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M15 10v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M17.84 7.17a4 4 0 0 0-5.66 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M20.66 4.34a8 8 0 0 0-11.31 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </Icon>
  );
}

export function PinIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 17v5" />
        <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
      </svg>
    </Icon>
  );
}

export function PinOffIcon({ size = 14, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 17v5" />
        <path d="M15 9.34V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H7.89" />
        <path d="m2 2 20 20" />
        <path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h11" />
      </svg>
    </Icon>
  );
}

export function StatusIcon({ kind, size = 10, className = "" }) {
  const color =
    kind === "working"
      ? "var(--color-success)"
      : kind === "error"
        ? "var(--color-danger)"
        : null;
  const cls = kind === "working"
    ? `${className} ${iconStyles.pulse}`.trim()
    : className;
  return (
    <Icon size={size} color={color} className={cls}>
      <svg viewBox="0 0 10 10" fill="none">
        {kind === "done" && (
          <path
            d="M2 5.2l1.9 1.9L8 3"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {kind === "working" && <circle cx="5" cy="5" r="2.5" fill="currentColor" />}
        {kind === "error" && (
          <>
            <circle cx="5" cy="5" r="4" fill="currentColor" />
            <rect x="4.4" y="2.4" width="1.2" height="3.4" rx="0.4" fill="var(--color-bg-solid)" />
            <rect x="4.4" y="6.6" width="1.2" height="1.2" rx="0.4" fill="var(--color-bg-solid)" />
          </>
        )}
        {kind === "paused" && (
          <>
            <rect x="2.5" y="2" width="1.6" height="6" rx="0.4" fill="currentColor" />
            <rect x="5.9" y="2" width="1.6" height="6" rx="0.4" fill="currentColor" />
          </>
        )}
      </svg>
    </Icon>
  );
}

export function SpinnerIcon({ size = 12, className = "" }) {
  return (
    <Icon size={size} className={className}>
      <svg viewBox="0 0 12 12" fill="none">
        <circle
          cx="6"
          cy="6"
          r="4.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeDasharray="20 30"
          strokeLinecap="round"
        />
      </svg>
    </Icon>
  );
}
