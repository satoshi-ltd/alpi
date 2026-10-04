const RUN_STATUS = {
  between: { text: 'between phases' },
  completed: { text: 'completed' },
};

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
