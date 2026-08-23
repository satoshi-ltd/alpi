import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { Btn, Mono, Popover, Tip } from "./index.js";
import styles from "./RunsButton.module.css";

export default function RunsButton({ profile, connectionId = null }) {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    if (!profile) return;
    setLoading(true);
    setError("");
    try {
      const result = await invoke("runs_list", { profile, limit: 30, connectionId });
      setRuns(result?.runs ?? []);
    } catch {
      setRuns([]);
      setError("Runs unavailable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) load();
  }, [open, profile, connectionId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <span className={styles.root}>
      <Tip text="Durable runs — inspect or stop" side="r">
        <Btn variant="ghost" onClick={() => setOpen((value) => !value)}>Runs</Btn>
      </Tip>
      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-lg)" align="right">
        <div className={styles.scroll}>
          {loading && runs.length === 0 && <div className={styles.empty}>Loading runs…</div>}
          {!loading && runs.length === 0 && <div className={styles.empty}>{error || "No runs yet"}</div>}
          {runs.length > 0 && error && <div className={styles.empty}>{error}</div>}
          {runs.map((run) => (
            <button
              type="button"
              key={run.id}
              className={`row ${styles.row}`}
              disabled={run.status !== "running"}
              onClick={async () => {
                try {
                  setError("");
                  await invoke("run_cancel", { profile, id: run.id, connectionId });
                  await load();
                } catch {
                  setError("Could not stop run");
                }
              }}
            >
              <span className={styles.label}>{run.status === "running" ? "●" : "○"} {run.id}</span>
              <Mono>{run.status}</Mono>
              <span className={styles.meta}>{run.source || "user"} · {run.model || "-"} · {run.event_count ?? 0} events</span>
            </button>
          ))}
        </div>
      </Popover>
    </span>
  );
}
