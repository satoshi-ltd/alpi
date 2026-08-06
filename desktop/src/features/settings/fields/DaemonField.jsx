import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { useNotify } from "../../../primitives/Notification.jsx";
import ConfirmDelete from "../../../primitives/ConfirmDelete.jsx";
import { Button } from "../../../primitives/index.js";

export function DaemonField() {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const [confirming, setConfirming] = useState(false);

  async function restart() {
    if (busy) return;
    setBusy("restart");
    try {
      await invoke("daemon_restart");
      notify({ message: "Daemon restarting…", variant: "info", duration: 3000 });
    } catch (e) {
      notify({ message: `restart: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  async function update() {
    if (busy) return;
    setBusy("update");
    try {
      const res = await invoke("daemon_update");
      if (res?.updated) {
        notify({ message: `Updating to v${res.latest} — daemon restarting…`, variant: "info", duration: 3000 });
      } else if (res?.reason === "up-to-date") {
        notify({ message: `Already on the latest (v${res.current})`, variant: "info", duration: 2500 });
      } else if (res?.reason === "manual") {
        notify({ message: "Can't self-update — image-pinned (Docker). Repull the image to update.", variant: "error", duration: 5000 });
      } else {
        notify({ message: `Update failed: ${res?.reason || "unknown"}`, variant: "error", duration: 5000 });
      }
    } catch (e) {
      notify({ message: `update: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  return (
    <span className="row row-gap">
      <Button onClick={update} disabled={!!busy} variant="ghost" size="sm">
        {busy === "update" ? "Updating…" : "Update alpi"}
      </Button>
      <Button onClick={() => setConfirming(true)} disabled={!!busy} variant="ghost" size="sm">
        {busy === "restart" ? "Restarting…" : "Restart daemon"}
      </Button>
      <ConfirmDelete
        open={confirming}
        onClose={() => setConfirming(false)}
        onConfirm={restart}
        title="Restart the daemon?"
        consequence="Every connected client briefly loses its socket; agent loops mid-turn stop and resume on next request."
        typeToConfirm="restart"
        confirmLabel="Restart"
      />
    </span>
  );
}
