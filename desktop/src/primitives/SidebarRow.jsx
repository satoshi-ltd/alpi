import { Diamond, Hash, Mono, MuteIcon } from "./index.js";
import styles from "./SidebarRow.module.css";

export default function SidebarRow({
  kind = "profile",
  id,
  color,
  sel = false,
  colorWash = false,
  onClick,
  onContextMenu,
  trailing,
  leading,
  muted = false,
}) {
  const tinted = sel && colorWash && color;
  const background = tinted
    ? `color-mix(in srgb, ${color} ${kind === "workgroup" ? "14%" : "18%"}, var(--bg-side))`
    : sel
      ? "var(--selected)"
      : null;
  const textColor = tinted
    ? kind === "profile"
      ? `color-mix(in srgb, ${color} 90%, var(--ink))`
      : "var(--ink)"
    : muted
      ? "var(--ink-3)"
      : "var(--ink)";
  // Background + textColor are runtime-derived (color-mix + props) — kept inline.
  return (
    <button
      type="button"
      className="ds-sb-row"
      onClick={onClick}
      onContextMenu={onContextMenu}
      style={{
        ...(background ? { background } : {}),
        color: textColor,
        opacity: muted ? 0.55 : undefined,
      }}
    >
      {leading !== undefined
        ? leading
        : kind === "workgroup"
          ? (
              <span className={styles.glyphSlot}>
                <Hash />
              </span>
            )
          : <Diamond color={color} />}
      <span className={`${styles.label} ${tinted ? styles.tinted : ""}`}>
        {kind === "workgroup" ? <Mono>{`#${id}`}</Mono> : id}
      </span>
      {muted && <MuteIcon className={styles.mute} />}
      {trailing !== undefined && trailing !== null && (
        <span className="sb-row-trailing">{trailing}</span>
      )}
    </button>
  );
}
