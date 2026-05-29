import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { useNotify } from "../../../primitives/Notification.jsx";
import ConfirmDelete from "../../../primitives/ConfirmDelete.jsx";
import { Button } from "../../../primitives/index.js";

export function DaemonField() {
  const notify = useNotify();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  async function restart() {
    if (busy) return;
    setBusy(true);
    try {
      await invoke("daemon_restart");
      notify({ message: "Daemon restarting…", variant: "info", duration: 3000 });
    } catch (e) {
      notify({ message: `restart: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <span>
      <Button onClick={() => setConfirming(true)} disabled={busy} variant="ghost" size="sm">
        {busy ? "Restarting…" : "Restart daemon"}
      </Button>
      <ConfirmDelete
        mode="typed"
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
