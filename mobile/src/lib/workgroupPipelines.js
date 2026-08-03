export function runPhases(run) {
  const phases = Array.isArray(run?.phases) ? run.phases : [];
  const blocked = run?.status === 'blocked';
  return phases.map((p) => ({
    slug: String(p?.slug ?? ''),
    state: blocked && p?.state === 'current' ? 'blocked' : String(p?.state ?? 'pending'),
    seq: typeof p?.seq === 'number' ? p.seq : null,
  }));
}

export function activePhaseIndex(phases) {
  const list = Array.isArray(phases) ? phases : [];
  if (!list.length) return 0;
  const blocked = list.findIndex((p) => p.state === 'blocked');
  if (blocked >= 0) return blocked;
  const current = list.findIndex((p) => p.state === 'current');
  if (current >= 0) return current;
  let last = 0;
  list.forEach((p, i) => {
    if (p.state === 'completed' || p.state === 'skipped') last = i;
  });
  return last;
}

export function namedPipelines(workgroup) {
  const map = workgroup?.pipelines && typeof workgroup.pipelines === 'object' ? workgroup.pipelines : {};
  const launch = workgroup?.launch_pipeline ?? null;
  const steps = workgroup?.phase_map && typeof workgroup.phase_map === 'object' ? workgroup.phase_map : {};
  const keys = Object.keys(map).filter((k) => Array.isArray(map[k]) && map[k].length > 0);
  keys.sort((a, b) => {
    if (a === launch) return -1;
    if (b === launch) return 1;
    return a.localeCompare(b);
  });
  return keys.map((key) => {
    const phases = map[key].map((s) => String(s));
    const spec = steps[phases[0]] ?? {};
    const owner = String(spec.owner ?? '').trim();
    const task = String(spec.task ?? '').trim();
    return {
      key,
      phases,
      isLaunch: key === launch,
      owner,
      task,
      triggerable: !!(owner && task),
    };
  });
}

export function isLaunchless(workgroup) {
  const chains = namedPipelines(workgroup);
  return chains.length > 0 && !workgroup?.launch_pipeline;
}

export function triggerableChains(workgroup) {
  return namedPipelines(workgroup).filter((c) => c.triggerable);
}

export function triggerBlock(workgroup, tasks) {
  if (!workgroup?.is_hub) {
    return { reason: 'not-hub', message: 'only the hub can start a pipeline' };
  }
  if (workgroup?.paused) {
    return { reason: 'paused', message: 'resume the workgroup before starting a pipeline' };
  }
  const active = tasks?.active;
  if (active?.slug) {
    return { reason: 'busy', message: `#${active.slug} is still open — a trigger never preempts work` };
  }
  return null;
}

export function runActionLabel(key, run) {
  return run?.pipeline === key && run?.status === 'completed' ? 'Run again' : 'Run';
}

export function runStateLabel(key, run) {
  if (run?.pipeline !== key) return null;
  const status = String(run?.status ?? '');
  const phase = String(run?.current_phase ?? '');
  if (!status) return null;
  if (status === 'completed') return 'completed';
  return phase ? `${status} · #${phase}` : status;
}

export function runRestartsChain(key, run) {
  return run?.pipeline === key && run?.status !== 'completed';
}

export function triggerSummary(chain, run) {
  const phases = Array.isArray(chain?.phases) ? chain.phases : [];
  const first = phases[0] ?? '';
  const parts = [
    `@${chain?.owner} opens #${first} with the task the recipe declares: "${chain?.task}".`,
    `${phases.length} ${phases.length === 1 ? 'phase' : 'phases'} run in order.`,
  ];
  if (runRestartsChain(chain?.key, run)) {
    parts.push(`#${chain?.key} is unfinished — this restarts it from #${first}, it does not resume.`);
  }
  return parts.join(' ');
}

export function triggerPipeline(call, { profile, wgId, pipeline }) {
  return call('host.workgroup.trigger', { profile, wg_id: wgId, pipeline });
}

export async function runPipelineTrigger(call, { workgroup, chain }) {
  try {
    const result = await triggerPipeline(call, {
      profile: workgroup?.profile ?? null,
      wgId: workgroup?.id ?? null,
      pipeline: chain?.key,
    });
    return {
      ok: true,
      pipeline: result?.pipeline ?? chain?.key,
      phase: result?.phase ?? chain?.phases?.[0] ?? null,
      seq: typeof result?.seq === 'number' ? result.seq : null,
    };
  } catch (e) {
    return {
      ok: false,
      code: e?.message ? String(e.message) : 'pipeline-trigger-rejected',
      message: daemonMessage(e),
    };
  }
}

export function daemonMessage(error) {
  const detail = error?.data?.detail;
  if (detail) return String(detail);
  const message = error?.message;
  return message ? String(message) : 'trigger rejected';
}
