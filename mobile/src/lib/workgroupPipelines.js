const RUN_STATUS = {
  between: { tone: 'off', text: 'between phases' },
  blocked: { tone: 'err', text: 'blocked' },
  completed: { tone: 'on', text: 'completed' },
};

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
  const current = phases.findIndex((p) => p.state === 'current');
  if (current >= 0) return current;
  const lastDone = phases.map((p) => p.state).lastIndexOf('done');
  return lastDone >= 0 ? lastDone : 0;
}

export function runStatus(run) {
  return RUN_STATUS[String(run?.status ?? '')] ?? null;
}

export function phaseJumpable(phase, loadedSeqs) {
  return phase?.seq != null && !!loadedSeqs?.has?.(phase.seq);
}

export function phaseUnavailable(phase) {
  const slug = String(phase?.slug ?? '');
  if (phase?.seq == null) return `#${slug} has not opened yet — nothing to jump to`;
  return `#${slug} opened at post #${phase.seq}, outside the loaded history`;
}

export function namedPipelines(workgroup) {
  const map = workgroup?.pipelines && typeof workgroup.pipelines === 'object' ? workgroup.pipelines : {};
  const launch = workgroup?.launch_pipeline ?? null;
  const keys = Object.keys(map).filter((k) => Array.isArray(map[k]) && map[k].length > 0);
  keys.sort((a, b) => {
    if (a === launch) return -1;
    if (b === launch) return 1;
    return a.localeCompare(b);
  });
  return keys.map((key) => ({
    key,
    phases: map[key].map((s) => String(s)),
    isLaunch: key === launch,
  }));
}

export function isLaunchless(workgroup) {
  const chains = namedPipelines(workgroup);
  return chains.length > 0 && !workgroup?.launch_pipeline;
}
