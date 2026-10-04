import { WORKGROUP_FOLD } from "../../../common/folds.mjs";
import { Fold, MuteIcon } from "./index.js";
import styles from "./SidebarRow.module.css";

export default function SidebarRow({
  kind = "profile",
  id,
  color,
  fold,
  sel = false,
  unread = false,
  colorWash = false,
  onClick,
  onContextMenu,
  trailing,
  leading,
  muted = false,
  state,
  ariaLabel,
}) {
  const isNeedsProvider = state === "needs-provider";
  const tinted = sel && colorWash && color;
  const background = tinted
    ? `color-mix(in srgb, ${color} ${kind === "workgroup" ? "14%" : "18%"}, var(--bg-side))`
    : sel
      ? "var(--bg-pane)"
      : null;
  const tintedColor = tinted
    ? kind === "profile"
      ? `color-mix(in srgb, ${color} 90%, var(--ink))`
      : "var(--ink)"
    : null;
  const stateMod = unread ? " is-unr" : sel ? " is-sel" : "";
  return (
    <button
      type="button"
      className="ds-sb-row"
      data-sel={sel || undefined}
      data-state={state || undefined}
      aria-label={ariaLabel || undefined}
      onClick={onClick}
      onContextMenu={onContextMenu}
      style={{
        ...(background ? { background } : {}),
        ...(tintedColor ? { color: tintedColor } : {}),
        ...(muted && !isNeedsProvider ? { opacity: "var(--alpha-muted)" } : {}),
      }}
    >
      {leading !== undefined ? (
        leading
      ) : (
        <span className={styles.glyphSlot}>
          <Fold fold={kind === "workgroup" ? WORKGROUP_FOLD : fold} color={color} outlined={isNeedsProvider} />
        </span>
      )}
      <span
        className={`sb-name${stateMod} ${styles.label}`.trim()}
        style={tintedColor ? { color: "inherit" } : undefined}
      >
        {id}
      </span>
      {muted && !isNeedsProvider && <MuteIcon className={styles.mute} />}
      {trailing !== undefined && trailing !== null && (
        <span className="sb-row-trailing">{trailing}</span>
      )}
    </button>
  );
}
