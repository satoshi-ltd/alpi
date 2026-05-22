import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Section } from "../primitives.jsx";
import { ScheduleRow as DsScheduleRow } from "../../../primitives/SettingsLayout.jsx";
import { scheduleSummary } from "../util.js";

export function SchedulesSection({ profile }) {
  const [jobs, setJobs] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const notify = useNotify();

  async function load() {
    try {
      const list = await invoke("schedules", { profile: profile.name });
      setJobs(Array.isArray(list) ? list : []);
    } catch {
      setJobs([]);
    }
  }

  useEffect(() => { load(); }, [profile.name]);

  async function fire(id) {
    setBusyId(`fire:${id}`);
    try {
      await invoke("schedule_fire", { profile: profile.name, id });
      notify({ message: `Schedule ${id} started`, variant: "success", duration: 2000 });
      await load();
    } catch (e) {
      notify({ message: `fire failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusyId(null);
    }
  }

  async function setPaused(id, paused) {
    setBusyId(`pause:${id}`);
    try {
      await invoke("schedule_set_paused", { profile: profile.name, id, paused });
      await load();
    } catch (e) {
      notify({
        message: `${paused ? "pause" : "resume"} failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusyId(null);
    }
  }

  async function remove(id) {
    setBusyId(`del:${id}`);
    try {
      await invoke("schedule_remove", { profile: profile.name, id });
      await load();
    } catch (e) {
      notify({ message: `delete failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusyId(null);
    }
  }

  if (jobs === null || jobs.length === 0) return null;
  return (
    <Section title="Schedule">
      <div className="col" style={{ gap: 0 }}>
        {jobs.map((j) => (
          <DsScheduleRow
            key={j.id}
            s={{
              id: j.id,
              cron: scheduleSummary(j),
              desc: j.prompt || "",
              on: !j.paused,
              noAgent: Boolean(j.no_agent),
            }}
            onFire={() => fire(j.id)}
            onToggle={() => setPaused(j.id, !j.paused)}
            onDelete={() => remove(j.id)}
          />
        ))}
      </div>
    </Section>
  );
}
