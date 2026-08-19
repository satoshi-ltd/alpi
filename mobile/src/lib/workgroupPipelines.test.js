import { describe, expect, it } from 'vitest';

import {
  isLaunchless,
  namedPipelines,
  phaseJumpable,
  phaseUnavailable,
  runPhases,
  runStatus,
} from './workgroupPipelines';

const WG = {
  id: 'wg1',
  profile: 'mira',
  is_hub: true,
  paused: false,
  pipelines: {
    setup: ['setup', 'enrich', 'build', 'qa'],
    'media-update': ['media-update', 'media-config', 'media-build', 'media-qa'],
  },
  launch_pipeline: 'setup',
  pipeline_mode: true,
  phase_map: {
    setup: { owner: 'scout', task: 'collect the brief' },
    'media-update': { owner: 'pixel', task: 'refresh the photos' },
  },
};

const LAUNCH_RUN = {
  active: { slug: 'build', title: 'wire it', opened_seq: 12 },
  closed: [],
  blocked: null,
  pipeline_run: {
    pipeline: 'setup',
    status: 'running',
    started_seq: 4,
    current_phase: 'build',
    phases: [
      { slug: 'setup', state: 'completed', seq: 5 },
      { slug: 'enrich', state: 'completed', seq: 9 },
      { slug: 'build', state: 'current', seq: 12 },
      { slug: 'qa', state: 'pending', seq: null },
    ],
  },
};

const MAINTENANCE_RUN = {
  active: { slug: 'media-build', title: 'rebuild', opened_seq: 43 },
  closed: [],
  blocked: null,
  pipeline_run: {
    pipeline: 'media-update',
    status: 'running',
    started_seq: 37,
    current_phase: 'media-build',
    phases: [
      { slug: 'media-update', state: 'completed', seq: 40 },
      { slug: 'media-config', state: 'skipped', seq: 42 },
      { slug: 'media-build', state: 'current', seq: 43 },
      { slug: 'media-qa', state: 'pending', seq: null },
    ],
  },
};

const BETWEEN_RUN = {
  active: null,
  closed: [{ slug: 'enrich', result: 'done', closed_seq: 10, blocked: false }],
  blocked: null,
  pipeline_run: {
    pipeline: 'setup',
    status: 'between',
    started_seq: 4,
    current_phase: 'enrich',
    phases: [
      { slug: 'setup', state: 'completed', seq: 5 },
      { slug: 'enrich', state: 'completed', seq: 10 },
      { slug: 'build', state: 'pending', seq: null },
      { slug: 'qa', state: 'pending', seq: null },
    ],
  },
};

const BLOCKED_RUN = {
  active: null,
  closed: [{ slug: 'build', result: 'BLOCKED build · deps missing', closed_seq: 18, blocked: true }],
  blocked: { slug: 'build', reason: 'BLOCKED build · deps missing' },
  pipeline_run: {
    pipeline: 'setup',
    status: 'blocked',
    started_seq: 4,
    current_phase: 'build',
    phases: [
      { slug: 'setup', state: 'completed', seq: 5 },
      { slug: 'enrich', state: 'completed', seq: 9 },
      { slug: 'build', state: 'current', seq: 18 },
      { slug: 'qa', state: 'pending', seq: null },
    ],
  },
};

const COMPLETED_RUN = {
  active: null,
  closed: [{ slug: 'qa', result: 'green', closed_seq: 30, blocked: false }],
  blocked: null,
  pipeline_run: {
    pipeline: 'setup',
    status: 'completed',
    started_seq: 4,
    current_phase: 'qa',
    phases: [
      { slug: 'setup', state: 'completed', seq: 5 },
      { slug: 'enrich', state: 'skipped', seq: 9 },
      { slug: 'build', state: 'completed', seq: 18 },
      { slug: 'qa', state: 'completed', seq: 30 },
    ],
  },
};

const REPEAT_RUN = {
  active: { slug: 'setup', title: 'redo the brief', opened_seq: 51 },
  closed: [],
  blocked: null,
  pipeline_run: {
    pipeline: 'setup',
    status: 'running',
    started_seq: 51,
    current_phase: 'setup',
    phases: [
      { slug: 'setup', state: 'current', seq: 51 },
      { slug: 'enrich', state: 'pending', seq: null },
      { slug: 'build', state: 'pending', seq: null },
      { slug: 'qa', state: 'pending', seq: null },
    ],
  },
};

const ADHOC = {
  active: { slug: 'hotfix', title: 'patch the footer', opened_seq: 60 },
  closed: [],
  blocked: null,
  pipeline_run: null,
};

describe('runPhases', () => {
  it('keeps the daemon states of a launch run verbatim', () => {
    expect(runPhases(LAUNCH_RUN.pipeline_run)).toEqual([
      { slug: 'setup', state: 'completed', seq: 5 },
      { slug: 'enrich', state: 'completed', seq: 9 },
      { slug: 'build', state: 'current', seq: 12 },
      { slug: 'qa', state: 'pending', seq: null },
    ]);
  });

  it('keeps skipped distinct from completed on a maintenance run', () => {
    const phases = runPhases(MAINTENANCE_RUN.pipeline_run);
    expect(phases.map((p) => p.state)).toEqual(['completed', 'skipped', 'current', 'pending']);
  });

  it('renders the current phase of a blocked run as blocked', () => {
    const phases = runPhases(BLOCKED_RUN.pipeline_run);
    expect(phases.map((p) => p.state)).toEqual(['completed', 'completed', 'blocked', 'pending']);
    expect(phases[2].seq).toBe(18);
  });

  it('a completed run has no current phase', () => {
    const phases = runPhases(COMPLETED_RUN.pipeline_run);
    expect(phases.every((p) => p.state === 'completed' || p.state === 'skipped')).toBe(true);
  });

  it('a between run has no current phase', () => {
    expect(runPhases(BETWEEN_RUN.pipeline_run).some((p) => p.state === 'current')).toBe(false);
  });

  it('an ad-hoc task hides the strip', () => {
    expect(runPhases(ADHOC.pipeline_run)).toEqual([]);
    expect(runPhases(null)).toEqual([]);
  });
});

describe('runStatus', () => {
  it('names the states desktop labels, tone included', () => {
    expect(runStatus(BETWEEN_RUN.pipeline_run)).toEqual({ tone: 'off', text: 'between phases' });
    expect(runStatus(BLOCKED_RUN.pipeline_run)).toEqual({ tone: 'err', text: 'blocked' });
    expect(runStatus(COMPLETED_RUN.pipeline_run)).toEqual({ tone: 'on', text: 'completed' });
  });

  it('stays silent while a phase is running — the phase chain already says it', () => {
    expect(runStatus(LAUNCH_RUN.pipeline_run)).toBeNull();
    expect(runStatus(MAINTENANCE_RUN.pipeline_run)).toBeNull();
  });

  it('stays silent for a status it does not know and for no run at all', () => {
    expect(runStatus({ status: 'reticulating' })).toBeNull();
    expect(runStatus(null)).toBeNull();
  });
});

describe('phaseJumpable', () => {
  it('jumps only to a phase whose post the thread already loaded', () => {
    const phases = runPhases(MAINTENANCE_RUN.pipeline_run);
    const loaded = new Set([42, 43]);
    expect(phases.filter((p) => phaseJumpable(p, loaded)).map((p) => p.slug))
      .toEqual(['media-config', 'media-build']);
  });

  it('never jumps to a phase that never opened', () => {
    expect(phaseJumpable({ slug: 'qa', seq: null }, new Set([null]))).toBe(false);
  });

  it('never jumps when the thread reports no loaded history', () => {
    expect(phaseJumpable({ slug: 'build', seq: 12 }, undefined)).toBe(false);
    expect(phaseJumpable({ slug: 'build', seq: 12 }, new Set())).toBe(false);
  });
});

describe('phaseUnavailable', () => {
  it('says a pending phase has nothing to jump to', () => {
    expect(phaseUnavailable({ slug: 'qa', seq: null }))
      .toBe('#qa has not opened yet — nothing to jump to');
  });

  it('says where an unloaded phase opened', () => {
    expect(phaseUnavailable({ slug: 'setup', seq: 5 }))
      .toBe('#setup opened at post #5, outside the loaded history');
  });
});

describe('namedPipelines', () => {
  it('lists every declared chain with the launch chain first', () => {
    const chains = namedPipelines(WG);
    expect(chains.map((c) => c.key)).toEqual(['setup', 'media-update']);
    expect(chains[0].isLaunch).toBe(true);
    expect(chains[1].isLaunch).toBe(false);
    expect(chains[1].phases).toEqual(['media-update', 'media-config', 'media-build', 'media-qa']);
  });

  it('carries no launch contract — mobile cannot start a chain', () => {
    expect(Object.keys(namedPipelines(WG)[0])).toEqual(['key', 'phases', 'isLaunch']);
  });

  it('is empty for a manual deliberation workgroup', () => {
    expect(namedPipelines({ id: 'w', pipelines: {}, launch_pipeline: null })).toEqual([]);
    expect(namedPipelines(null)).toEqual([]);
  });

  it('never reads a retired pipeline list', () => {
    expect(namedPipelines({ id: 'w', pipeline: ['intake', 'build'], pipelines: {} })).toEqual([]);
  });
});

describe('isLaunchless', () => {
  it('is true when chains are declared but none is the launch chain', () => {
    const wg = { ...WG, launch_pipeline: null };
    expect(isLaunchless(wg)).toBe(true);
    expect(namedPipelines(wg).every((c) => !c.isLaunch)).toBe(true);
  });

  it('is false with a launch chain and false without any chain', () => {
    expect(isLaunchless(WG)).toBe(false);
    expect(isLaunchless({ pipelines: {}, pipeline_mode: false })).toBe(false);
  });
});
