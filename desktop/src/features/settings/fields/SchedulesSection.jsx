import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Section } from "../primitives.jsx";
import settingsStyles from "../Settings.module.css";
import { ScheduleRow as DsScheduleRow, ScheduleList as DsScheduleList } from "../../../primitives/SettingsLayout.jsx";
import { scheduleSummary } from "../util.js";

export function SchedulesSection({ profile, connectionId = null }) {
  const [jobs, setJobs] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const notify = useNotify();
  const targetRef = useRef({ profile: profile.name, connectionId });
  const genRef = useRef(0);

  const connArg = connectionId ? { connectionId } : {};

  async function load() {
    const gen = genRef.current;
    try {
      const list = await invoke("schedules", { profile: profile.name, ...connArg });
      if (gen !== genRef.current) return;
      setJobs(Array.isArray(list) ? list : []);
      setLoadError(null);
    } catch (e) {
      if (gen !== genRef.current) return;
      setJobs([]);
      setLoadError(String(e));
    }
  }

  useEffect(() => {
    genRef.current += 1;
    targetRef.current = { profile: profile.name, connectionId };
    setJobs(null);
    setLoadError(null);
    setBusyId(null);
    load();
  }, [profile.name, connectionId]);

  function pinnedTarget() {
    return {
      profile: targetRef.current.profile,
      ...(targetRef.current.connectionId ? { connectionId: targetRef.current.connectionId } : {}),
    };
  }

  async function fire(id) {
    const gen = genRef.current;
    const target = pinnedTarget();
    setBusyId(`fire:${id}`);
    try {
      await invoke("schedule_fire", { ...target, id });
      if (gen !== genRef.current) return;
      notify({ message: `Schedule ${id} started`, variant: "success", duration: 2000 });
      await load();
    } catch (e) {
      if (gen !== genRef.current) return;
      notify({ message: `fire failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      if (gen === genRef.current) setBusyId(null);
    }
  }

  async function setPaused(id, paused) {
    const gen = genRef.current;
    const target = pinnedTarget();
    setBusyId(`pause:${id}`);
    try {
      await invoke("schedule_set_paused", { ...target, id, paused });
      if (gen !== genRef.current) return;
      await load();
    } catch (e) {
      if (gen !== genRef.current) return;
      notify({
        message: `${paused ? "pause" : "resume"} failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      if (gen === genRef.current) setBusyId(null);
    }
  }

  async function remove(id) {
    const gen = genRef.current;
    const target = pinnedTarget();
    setBusyId(`del:${id}`);
    try {
      await invoke("schedule_remove", { ...target, id });
      if (gen !== genRef.current) return;
      await load();
    } catch (e) {
      if (gen !== genRef.current) return;
      notify({ message: `delete failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      if (gen === genRef.current) setBusyId(null);
    }
  }

  if (loadError) {
    return (
      <Section title="Schedule" tooltip="recurring agent tasks">
        <div role="alert" className={settingsStyles.error}>
          Could not load schedule: {loadError}
        </div>
      </Section>
    );
  }
  if (jobs === null || jobs.length === 0) return null;
  return (
    <Section title="Schedule" tooltip="recurring agent tasks">
      <DsScheduleList>
        {jobs.map((j) => (
          <DsScheduleRow
            key={j.id}
            s={{
              id: j.id,
              cron: scheduleSummary(j),
              title: j.title || "",
              prompt: j.prompt || "",
              on: !j.paused,
            }}
            onFire={() => fire(j.id)}
            onToggle={() => setPaused(j.id, !j.paused)}
            onDelete={() => remove(j.id)}
          />
        ))}
      </DsScheduleList>
    </Section>
  );
}
