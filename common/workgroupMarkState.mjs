import { phaseOwner, runProgress } from "./pipelinePhases.mjs";
import { WG_GAP, WG_GAP_PX, WG_ORDER } from "./workgroupMark.mjs";

const RUNNING = new Set(["running", "between"]);

export function workgroupGap(px) {
  return Math.round(Math.max(WG_GAP, (WG_GAP_PX * 100) / px) * 10) / 10;
}

export function currentCell(phase) {
  const [done, total] = phase ?? [];
  if (!(total > 0) || !(done >= 0)) return null;
  return WG_ORDER[Math.min(2, Math.floor((3 * done) / total))];
}

export function workgroupPhase(run) {
  const done = run?.phasesDone ?? run?.phases_done;
  const total = run?.phasesTotal ?? run?.phases_total;
  return Number.isInteger(done) && Number.isInteger(total) && total > 0 ? [Math.min(done, total), total] : null;
}

export function workgroupMarkState({ workgroup, run = null, task = null, busy = false, offline = false }) {
  if (workgroup?.paused) return "paused";
  if (offline) return "offline";
  const status = workgroup?.pipeline_status;
  if (status === "blocked") return "needs";
  if (status === "queued") return "queued";
  if (run || busy || RUNNING.has(status) || task?.state === "open") return "running";
  if (task?.state === "error") return "failed";
  return "idle";
}

function phaseSlug(workgroup, run) {
  return run?.phase ?? workgroup?.pipeline_phase ?? null;
}

export function phaseOwnerName(workgroup, run = null) {
  const slug = phaseSlug(workgroup, run);
  return slug ? phaseOwner(workgroup?.phase_map, slug) : null;
}

export function workgroupMark({ workgroup, run = null, task = null, busy = false, offline = false }) {
  const state = workgroupMarkState({ workgroup, run, task, busy, offline });
  const lit = state === "running" || state === "needs";
  const owner = lit ? phaseOwnerName(workgroup, run) : null;
  return { state, phase: workgroupPhase(run), step: lit ? phaseSlug(workgroup, run) : null, owner: owner ? owner.replace(/^@/, "") : null };
}

export function workgroupStatusLine(mark) {
  const word = mark?.state === "running" ? "Working" : mark?.state === "needs" ? "Needs you" : null;
  if (!word) return null;
  return withOwner(mark.step ? `${word} · ${mark.step}` : word, mark.owner);
}

export function withOwner(label, owner) {
  const name = owner ? String(owner).replace(/^@/, "") : "";
  return name ? `${label} · @${name}` : label;
}

export function pipelineRunMark({ workgroup, pipelineRun = null, task = null, busy = false, offline = false }) {
  const status = pipelineRun?.status ?? workgroup?.pipeline_status;
  const progress = runProgress(pipelineRun);
  const live = progress && (RUNNING.has(status) || status === "blocked");
  const run = live ? { phasesDone: progress.done, phasesTotal: progress.total, phase: pipelineRun.current_phase ?? workgroup?.pipeline_phase ?? null } : null;
  const merged = workgroup ? { ...workgroup, pipeline_status: status } : workgroup;
  return workgroupMark({ workgroup: merged, run, task, busy, offline });
}
