import { describe, expect, it, vi } from 'vitest';

import {
  activePhaseIndex,
  daemonMessage,
  isLaunchless,
  namedPipelines,
  runActionLabel,
  runPhases,
  runPipelineTrigger,
  runRestartsChain,
  runStateLabel,
  triggerBlock,
  triggerPipeline,
  triggerSummary,
  triggerableChains,
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

describe('activePhaseIndex', () => {
  it('targets the current phase', () => {
    expect(activePhaseIndex(runPhases(LAUNCH_RUN.pipeline_run))).toBe(2);
  });

  it('targets the blocked phase', () => {
    expect(activePhaseIndex(runPhases(BLOCKED_RUN.pipeline_run))).toBe(2);
  });

  it('targets the last closed phase between phases', () => {
    expect(activePhaseIndex(runPhases(BETWEEN_RUN.pipeline_run))).toBe(1);
  });

  it('targets the last phase of a completed run', () => {
    expect(activePhaseIndex(runPhases(COMPLETED_RUN.pipeline_run))).toBe(3);
  });

  it('resets to the first phase when the chain restarts', () => {
    expect(activePhaseIndex(runPhases(REPEAT_RUN.pipeline_run))).toBe(0);
  });

  it('is 0 for an empty strip', () => {
    expect(activePhaseIndex([])).toBe(0);
  });
});

describe('runActionLabel', () => {
  it('says Run again only once the visible run completed', () => {
    expect(runActionLabel('setup', LAUNCH_RUN.pipeline_run)).toBe('Run');
    expect(runActionLabel('setup', { pipeline: 'setup', status: 'between' })).toBe('Run');
    expect(runActionLabel('setup', { pipeline: 'setup', status: 'blocked' })).toBe('Run');
    expect(runActionLabel('setup', { pipeline: 'setup', status: 'completed' })).toBe('Run again');
    expect(runActionLabel('media-update', { pipeline: 'setup', status: 'completed' })).toBe('Run');
    expect(runActionLabel('setup', null)).toBe('Run');
  });

  it('surfaces the run state instead of leaving an unfinished chain looking idle', () => {
    expect(runStateLabel('setup', { pipeline: 'setup', status: 'running', current_phase: 'build' }))
      .toBe('running · #build');
    expect(runStateLabel('setup', { pipeline: 'setup', status: 'blocked', current_phase: 'qa' }))
      .toBe('blocked · #qa');
    expect(runStateLabel('setup', { pipeline: 'setup', status: 'completed', current_phase: 'qa' }))
      .toBe('completed');
    expect(runStateLabel('media-update', { pipeline: 'setup', status: 'running' })).toBeNull();
    expect(runStateLabel('setup', null)).toBeNull();
  });

  it('warns that an unfinished chain restarts rather than resumes', () => {
    expect(runRestartsChain('setup', { pipeline: 'setup', status: 'blocked' })).toBe(true);
    expect(runRestartsChain('setup', { pipeline: 'setup', status: 'completed' })).toBe(false);
    expect(runRestartsChain('media-update', { pipeline: 'setup', status: 'blocked' })).toBe(false);
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

  it('marks a chain triggerable only when its first phase declares owner and task', () => {
    const chains = namedPipelines({
      ...WG,
      phase_map: { setup: { owner: 'scout', task: 'collect' }, 'media-update': { owner: 'pixel' } },
    });
    expect(chains.find((c) => c.key === 'setup').triggerable).toBe(true);
    expect(chains.find((c) => c.key === 'media-update').triggerable).toBe(false);
  });

  it('is empty for a manual deliberation workgroup', () => {
    expect(namedPipelines({ id: 'w', pipelines: {}, launch_pipeline: null })).toEqual([]);
    expect(namedPipelines(null)).toEqual([]);
  });

  it('never reads a retired pipeline list', () => {
    expect(namedPipelines({ id: 'w', pipeline: ['intake', 'build'], pipelines: {} })).toEqual([]);
  });
});

describe('triggerableChains', () => {
  it('keeps only the chains whose first phase declares owner and task', () => {
    expect(triggerableChains(WG).map((c) => c.key)).toEqual(['setup', 'media-update']);
    const partial = { ...WG, phase_map: { setup: { owner: 'scout', task: 'collect' }, 'media-update': {} } };
    expect(triggerableChains(partial).map((c) => c.key)).toEqual(['setup']);
  });

  it('is empty for a deliberation workgroup', () => {
    expect(triggerableChains({ pipelines: {}, launch_pipeline: null })).toEqual([]);
  });
});

describe('triggerSummary', () => {
  const chain = namedPipelines(WG)[1];

  it('names the owner, the first phase and the task the recipe declares', () => {
    const summary = triggerSummary(chain, null);
    expect(summary).toContain('@pixel');
    expect(summary).toContain('#media-update');
    expect(summary).toContain('refresh the photos');
    expect(summary).toContain('4 phases run in order');
    expect(summary).not.toContain('resume');
  });

  it('says an unfinished chain restarts instead of resuming', () => {
    const summary = triggerSummary(chain, { pipeline: 'media-update', status: 'blocked' });
    expect(summary).toContain('restarts it from #media-update');
    expect(summary).toContain('does not resume');
  });

  it('says nothing about restarting once the chain completed', () => {
    expect(triggerSummary(chain, { pipeline: 'media-update', status: 'completed' })).not.toContain('restarts');
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

describe('triggerBlock', () => {
  it('passes when the hub is active and idle', () => {
    expect(triggerBlock(WG, BETWEEN_RUN)).toBeNull();
  });

  it('blocks a subscriber', () => {
    expect(triggerBlock({ ...WG, is_hub: false }, BETWEEN_RUN).reason).toBe('not-hub');
  });

  it('blocks a paused workgroup', () => {
    expect(triggerBlock({ ...WG, paused: true }, BETWEEN_RUN).reason).toBe('paused');
  });

  it('blocks while a task is open', () => {
    const block = triggerBlock(WG, LAUNCH_RUN);
    expect(block.reason).toBe('busy');
    expect(block.message).toContain('#build');
  });

  it('blocks while an ad-hoc task is open', () => {
    expect(triggerBlock(WG, ADHOC).reason).toBe('busy');
  });
});

describe('triggerPipeline', () => {
  it('sends only the pipeline key — never an authored task post', async () => {
    const call = vi.fn(async () => ({ ok: true, pipeline: 'media-update', phase: 'media-update', seq: 61 }));
    const result = await triggerPipeline(call, { profile: 'mira', wgId: 'wg1', pipeline: 'media-update' });
    expect(call).toHaveBeenCalledTimes(1);
    const [method, params] = call.mock.calls[0];
    expect(method).toBe('host.workgroup.trigger');
    expect(params).toEqual({ profile: 'mira', wg_id: 'wg1', pipeline: 'media-update' });
    expect(Object.keys(params)).not.toContain('text');
    expect(JSON.stringify(params)).not.toContain('#task');
    expect(result.phase).toBe('media-update');
  });

  it('never falls back to host.workgroup.post', async () => {
    const call = vi.fn(async () => ({ ok: true }));
    await triggerPipeline(call, { profile: 'mira', wgId: 'wg1', pipeline: 'setup' });
    expect(call.mock.calls.map(([m]) => m)).not.toContain('host.workgroup.post');
  });
});

describe('runPipelineTrigger', () => {
  const chain = namedPipelines(WG)[1];

  it('reports the phase the daemon opened', async () => {
    const call = vi.fn(async () => ({ ok: true, pipeline: 'media-update', phase: 'media-update', seq: 61 }));
    const outcome = await runPipelineTrigger(call, { workgroup: WG, chain });
    expect(outcome).toEqual({ ok: true, pipeline: 'media-update', phase: 'media-update', seq: 61 });
    expect(call).toHaveBeenCalledWith('host.workgroup.trigger', {
      profile: 'mira',
      wg_id: 'wg1',
      pipeline: 'media-update',
    });
  });

  it('carries the daemon code and message for every rejection', async () => {
    const rejections = [
      ['pipeline-unknown', "'media-update' is not a declared pipeline"],
      ['workgroup-paused', 'resume the workgroup before starting a pipeline'],
      ['workgroup-busy', '`#build` is still open; a trigger never preempts work'],
      ['pipeline-trigger-not-hub', 'only the hub may start a pipeline in this workgroup'],
      ['pipeline-trigger-contract-missing', 'declares no owner/task for its first phase'],
      ['pipeline-trigger-rejected', 'workgroup budget exhausted'],
    ];
    for (const [code, detail] of rejections) {
      const call = vi.fn(async () => {
        throw Object.assign(new Error(code), { code: -32602, data: { detail } });
      });
      const outcome = await runPipelineTrigger(call, { workgroup: WG, chain });
      expect(outcome.ok).toBe(false);
      expect(outcome.code).toBe(code);
      expect(outcome.message).toBe(detail);
    }
  });

  it('never authors a post, even on rejection', async () => {
    const call = vi.fn(async () => {
      throw Object.assign(new Error('workgroup-busy'), { data: { detail: 'busy' } });
    });
    await runPipelineTrigger(call, { workgroup: WG, chain });
    expect(call).toHaveBeenCalledTimes(1);
    expect(call.mock.calls[0][0]).toBe('host.workgroup.trigger');
    expect(JSON.stringify(call.mock.calls[0][1])).not.toContain('#task');
  });
});

describe('daemonMessage', () => {
  it('surfaces the daemon detail for every stable rejection code', () => {
    const codes = {
      'pipeline-unknown': "'nope' is not a declared pipeline",
      'workgroup-paused': 'resume the workgroup before starting a pipeline',
      'workgroup-busy': '`#build` is still open; a trigger never preempts work',
      'pipeline-trigger-not-hub': 'only the hub may start a pipeline in this workgroup',
      'pipeline-trigger-contract-missing': 'pipeline declares no owner/task for its first phase',
      'pipeline-trigger-rejected': 'post rejected',
    };
    for (const [code, detail] of Object.entries(codes)) {
      const err = Object.assign(new Error(code), { code: -32602, data: { detail } });
      expect(daemonMessage(err)).toBe(detail);
    }
  });

  it('falls back to the error message when the daemon sent no detail', () => {
    expect(daemonMessage(new Error('workgroup-busy'))).toBe('workgroup-busy');
    expect(daemonMessage(null)).toBe('trigger rejected');
  });
});
