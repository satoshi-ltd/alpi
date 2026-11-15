import { WORKGROUP_SHAPE } from "../../../common/shapes.mjs";
import { Fold, MuteIcon } from "./index.js";
import styles from "./SidebarRow.module.css";

const STATE_WORD = { paused: "paused", "needs-provider": "needs provider" };

export default function SidebarRow({
  kind = "profile",
  id,
  color,
  shape,
  sel = false,
  unread = false,
  onClick,
  onContextMenu,
  trailing,
  leading,
  muted = false,
  state,
  ariaLabel,
}) {
  const isNeedsProvider = state === "needs-provider";
  const stateMod = unread ? " is-unr" : sel ? " is-sel" : "";
  return (
    <button
      type="button"
      className="ds-sb-row"
      data-sel={sel || undefined}
      aria-current={sel ? "page" : undefined}
      data-state={state || undefined}
      data-muted={muted && !isNeedsProvider ? "" : undefined}
      aria-label={ariaLabel || undefined}
      onClick={onClick}
      onContextMenu={onContextMenu}
    >
      {leading !== undefined ? (
        leading
      ) : (
        <span className={styles.glyphSlot}>
          <Fold shape={kind === "workgroup" ? WORKGROUP_SHAPE : shape} color={color} outlined={isNeedsProvider} still={!sel} />
        </span>
      )}
      <span
        className={`sb-name${stateMod} ${styles.label} ${STATE_WORD[state] ? styles.labelKeep : ""}`.trim()}
      >
        {id}
      </span>
      {STATE_WORD[state] && <span className={styles.stateWord}>{STATE_WORD[state]}</span>}
      {muted && !isNeedsProvider && <MuteIcon className={styles.mute} />}
      {trailing !== undefined && trailing !== null && (
        <span className="sb-row-trailing">{trailing}</span>
      )}
    </button>
  );
}
