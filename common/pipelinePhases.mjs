export function sameName(a, b) {
  return typeof a === "string" && typeof b === "string" && a.trim().toLowerCase() === b.trim().toLowerCase();
}

export function hasPhaseOwners(phaseMap) {
  return !!phaseMap && typeof phaseMap === "object" && Object.values(phaseMap).some((spec) => typeof spec?.owner === "string" && spec.owner.trim());
}

export function phaseOwner(phaseMap, slug) {
  const owner = phaseMap && typeof phaseMap === "object" ? phaseMap[slug]?.owner : null;
  return typeof owner === "string" && owner.trim() ? owner.trim() : null;
}

export function phaseTask(phaseMap, slug) {
  const task = phaseMap && typeof phaseMap === "object" ? phaseMap[slug]?.task : null;
  return typeof task === "string" && task.trim() ? task.trim() : null;
}

export function orderedPipelines(pipelines, launch) {
  const map = pipelines && typeof pipelines === "object" ? pipelines : {};
  const keys = Object.keys(map).filter((k) => Array.isArray(map[k]) && map[k].length > 0);
  return keys
    .sort((a, b) => (a === launch ? -1 : b === launch ? 1 : 0))
    .map((key) => ({ key, phases: map[key].map(String), isLaunch: key === launch }));
}

export function pipelineTrigger(isLaunch) {
  return isLaunch ? "starts at launch" : "on demand";
}

export function ownedPhases(phaseMap, pipelines, launch, name) {
  if (!name) return [];
  const out = [];
  for (const { phases } of orderedPipelines(pipelines, launch)) {
    for (const slug of phases) {
      if (sameName(phaseOwner(phaseMap, slug), name) && !out.includes(slug)) out.push(slug);
    }
  }
  return out;
}

export function runPhaseStates(run) {
  const states = new Map();
  if (!run || !Array.isArray(run.phases)) return states;
  const blocked = run.status === "blocked";
  for (const phase of run.phases) {
    const slug = String(phase?.slug ?? "");
    if (!slug) continue;
    const raw = String(phase?.state ?? "pending");
    states.set(slug, blocked && raw === "current" ? "blocked" : raw === "done" ? "completed" : raw);
  }
  return states;
}

export function chainChips(chain, phaseMap, run) {
  const states = run?.pipeline && Array.isArray(chain) ? runPhaseStates(run) : new Map();
  return (chain ?? []).map((slug) => ({
    slug,
    owner: phaseOwner(phaseMap, slug),
    state: states.get(slug) ?? "pending",
  }));
}

export function runSummary(run, key) {
  if (!run || run.pipeline !== key || !Array.isArray(run.phases) || run.phases.length === 0) return null;
  const states = [...runPhaseStates(run).values()];
  const done = states.filter((s) => s === "completed" || s === "skipped").length;
  const usd = Number(run.cost?.usd);
  const partial = run.cost_complete === false;
  const status = run.status === "running" ? "running" : run.status === "blocked" ? "blocked" : run.status === "completed" ? "completed" : "between phases";
  return {
    status,
    done,
    total: run.phases.length,
    cost: Number.isFinite(usd) && usd > 0 ? `$${usd.toFixed(2)}${partial ? " (declared only)" : ""}` : null,
  };
}

export function runSummaryLine(summary) {
  if (!summary) return "";
  return [`last run ${summary.status}`, `${summary.done} of ${summary.total}`, summary.cost].filter(Boolean).join(" · ");
}

export function runChips(run, phaseMap, active) {
  if (!run || !Array.isArray(run.phases)) return [];
  const states = runPhaseStates(run);
  const out = [];
  for (const phase of run.phases) {
    const slug = String(phase?.slug ?? "");
    if (!slug) continue;
    const owner = phaseOwner(phaseMap, slug);
    const state = states.get(slug) ?? "pending";
    const live = (state === "current" || state === "blocked") && active?.slug === slug;
    const routed = live && Array.isArray(active.assignees)
      ? active.assignees.filter((h) => typeof h === "string" && h.trim() && !sameName(h, owner))
      : [];
    out.push({
      slug,
      owner,
      state,
      assignee: routed[0] ?? null,
      seq: Number.isInteger(phase?.seq) ? phase.seq : null,
      cost: phase?.cost ?? null,
      task: phaseTask(phaseMap, slug),
    });
  }
  return out;
}

export function liveChip(chips) {
  return (chips ?? []).find((c) => c.state === "current" || c.state === "blocked") ?? null;
}

export function runProgress(run) {
  if (!run || !Array.isArray(run.phases) || run.phases.length === 0) return null;
  const done = [...runPhaseStates(run).values()].filter((s) => s === "completed" || s === "skipped").length;
  return { done, total: run.phases.length, label: `${done} of ${run.phases.length}` };
}

export function phaseCostLine(cost) {
  const usd = Number(cost?.usd);
  const tokens = Number(cost?.tokens);
  const parts = [];
  if (Number.isFinite(usd) && usd > 0) parts.push(`$${usd.toFixed(2)}`);
  if (Number.isFinite(tokens) && tokens > 0) parts.push(`${Math.round(tokens).toLocaleString("en-US")} tokens`);
  return parts.length ? parts.join(" · ") : null;
}

export function phaseWorker(chip) {
  return chip?.assignee ?? chip?.owner ?? null;
}
