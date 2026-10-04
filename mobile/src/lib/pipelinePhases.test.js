import { describe, expect, it } from 'vitest';
import { chainChips, liveChip, ownedPhases, runChips, runProgress, runSummary, runSummaryLine } from '../../../common/pipelinePhases.mjs';

const PIPELINES = { setup: ['setup', 'enrich', 'qa'], 'media-update': ['media-update', 'media-qa'] };
const PHASE_MAP = { setup: { owner: 'pixel' }, enrich: { owner: 'scout' }, qa: { owner: 'lens' }, 'media-qa': { owner: 'lens' } };

describe('pipeline phases on mobile', () => {
  it('derives owned phases, chip owners and states the same way as desktop', () => {
    expect(ownedPhases(PHASE_MAP, PIPELINES, 'setup', 'lens')).toEqual(['qa', 'media-qa']);
    const run = { pipeline: 'setup', status: 'blocked', phases: [{ slug: 'setup', state: 'completed' }, { slug: 'enrich', state: 'current' }] };
    expect(chainChips(PIPELINES.setup, PHASE_MAP, run).map((c) => [c.owner, c.state])).toEqual([
      ['pixel', 'completed'], ['scout', 'blocked'], ['lens', 'pending'],
    ]);
    expect(chainChips(['media-update'], PHASE_MAP, run)[0].owner).toBeNull();
    expect(runSummaryLine(runSummary(run, 'setup'))).toBe('last run blocked · 1 of 2');
  });
});

describe('run chips on mobile', () => {
  it('names the routed assignee and counts the run the same way as desktop', () => {
    const run = { pipeline: 'setup', status: 'running', phases: [{ slug: 'build', state: 'completed' }, { slug: 'qa', state: 'current' }] };
    expect(liveChip(runChips(run, { qa: { owner: 'lens' } }, { slug: 'qa', assignees: ['lingua'] }))).toMatchObject({ slug: 'qa', owner: 'lens', assignee: 'lingua' });
    expect(runProgress(run).label).toBe('1 of 2');
  });
});
