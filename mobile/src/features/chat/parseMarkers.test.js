import { describe, expect, it } from 'vitest';
import {
  buildTasks,
  classifyMessage,
  findBlocked,
  parseDone,
  parseSkip,
  parseTaskOpen,
  parseWorking,
  validateTaskShape,
} from './parseMarkers.js';

describe('parseTaskOpen', () => {
  it('returns null without a marker', () => {
    expect(parseTaskOpen('plain')).toBeNull();
    expect(parseTaskOpen('')).toBeNull();
    expect(parseTaskOpen(null)).toBeNull();
  });

  it('slug-less #task is no longer a task', () => {
    expect(parseTaskOpen('#task Ship ADR')).toBeNull();
    expect(parseTaskOpen('@forge #task Audit pipeline')).toBeNull();
  });

  it('extracts an explicit #slug and bolds it in content', () => {
    const post = '#task #onboarding-friction-top3 Top three onboarding friction points\n\nBody.';
    expect(parseTaskOpen(post)).toEqual({
      slug: 'onboarding-friction-top3',
      title: 'Top three onboarding friction points',
      content: '**#onboarding-friction-top3** Top three onboarding friction points\n\nBody.',
    });
  });

  it('accepts a slug without dashes', () => {
    expect(parseTaskOpen('#task #simple Title here')).toEqual({
      slug: 'simple',
      title: 'Title here',
      content: '**#simple** Title here',
    });
  });

  it('slug-only post (no title text)', () => {
    expect(parseTaskOpen('#task #icp-v2')).toEqual({
      slug: 'icp-v2',
      title: '',
      content: '**#icp-v2**',
    });
  });
});

describe('validateTaskShape', () => {
  it('passes through bodies without a #task marker', () => {
    expect(validateTaskShape('plain text')).toEqual({ ok: true });
    expect(validateTaskShape('')).toEqual({ ok: true });
    expect(validateTaskShape(null)).toEqual({ ok: true });
  });

  it('accepts well-formed #task #slug posts', () => {
    expect(validateTaskShape('#task #onboarding-friction-top3 …')).toEqual({ ok: true });
    expect(validateTaskShape('#task #icp-v2')).toEqual({ ok: true });
  });

  it('rejects #task without a slug', () => {
    const v = validateTaskShape('#task no slug here');
    expect(v.ok).toBe(false);
    expect(v.error).toMatch(/#<slug>/);
  });
});

describe('parseDone / parseWorking / parseSkip', () => {
  it('returns null when the marker is absent', () => {
    expect(parseDone('plain')).toBeNull();
    expect(parseWorking('plain')).toBeNull();
    expect(parseSkip('plain')).toBeNull();
  });

  it('keeps the full multi-line content after the marker', () => {
    const post = '#done Quórum completo.\n\n**1.** ORG.2 sube a #1.\n**2.** MEM.3 se mantiene.';
    expect(parseDone(post)).toEqual({
      content: 'Quórum completo.\n\n**1.** ORG.2 sube a #1.\n**2.** MEM.3 se mantiene.',
    });
  });

  it('strips @mentions before the marker', () => {
    expect(parseWorking('@hub #working fetching benchmarks')).toEqual({
      content: 'fetching benchmarks',
    });
  });

  it('accepts a bare marker with no trailing summary', () => {
    expect(parseSkip('#skip')).toEqual({ content: '' });
  });

  it('detects #done at the end of a multi-line synthesis (regression: hub closes with synthesis above)', () => {
    const post = 'Synthesis before closing.\n\n**Bet 1** — SplitPass.\n\n#done H2 bets framed as three hypotheses.';
    expect(parseDone(post)).toEqual({
      content: 'Synthesis before closing.\n\n**Bet 1** — SplitPass.\n\nH2 bets framed as three hypotheses.',
    });
  });
});

describe('classifyMessage', () => {
  it('routes #task with slug to the task branch', () => {
    const c = classifyMessage('#task #adr Ship ADR\n\nbody');
    expect(c.variant).toBe('task');
    expect(c.task?.slug).toBe('adr');
    expect(c.task?.content).toBe('**#adr** Ship ADR\n\nbody');
  });

  it('treats slug-less #task as plain prose', () => {
    const c = classifyMessage('#task Ship ADR');
    expect(c.variant).toBe('message');
  });

  it('routes #done with text content', () => {
    expect(classifyMessage('#done shipped\n\nmore detail')).toEqual({
      variant: 'done',
      text: 'shipped\n\nmore detail',
    });
  });

  it('treats a post with both #task and #done as prose (ambiguity rule)', () => {
    const c = classifyMessage('#task #combined Wrap\n#done shipped already');
    expect(c.variant).toBe('message');
  });
});

describe('buildTasks', () => {
  it('produces one entry per #task and reflects later #done', () => {
    const msgs = [
      { seq: 1, body: '#task #first First' },
      { seq: 2, body: 'noise' },
      { seq: 3, body: '#done all good' },
    ];
    const tasks = buildTasks(msgs);
    expect(tasks).toHaveLength(1);
    expect(tasks[0].title).toBe('First');
    expect(tasks[0].slug).toBe('first');
    expect(tasks[0].status).toBe('done');
    expect(tasks[0].msgs).toBe(3);
  });

  it('uses the explicit #slug as the task id when present', () => {
    const msgs = [
      { seq: 1, body: '#task #onboarding-friction-top3 Top three onboarding friction points' },
      { seq: 2, body: '#done shipped' },
    ];
    const tasks = buildTasks(msgs);
    expect(tasks[0].id).toBe('onboarding-friction-top3');
  });

  it('a peer #skip never closes the hub task', () => {
    const msgs = [
      { seq: 1, from_pubkey: 'hub', body: '#task #opener-voice Openers?' },
      { seq: 2, from_pubkey: 'peer', body: '#skip waiting on FX data' },
    ];
    const tasks = buildTasks(msgs, 'hub');
    expect(tasks).toHaveLength(1);
    expect(tasks[0].slug).toBe('opener-voice');
    expect(tasks[0].status).toBe('working');
  });

  it('a new hub #task preempts the previous one as skip', () => {
    const msgs = [
      { seq: 1, from_pubkey: 'hub', body: '#task #first First' },
      { seq: 2, from_pubkey: 'peer', body: 'some input' },
      { seq: 3, from_pubkey: 'hub', body: '#task #second Second' },
    ];
    const tasks = buildTasks(msgs, 'hub');
    expect(tasks).toHaveLength(2);
    expect(tasks[0].status).toBe('skip');
    expect(tasks[1].status).toBe('working');
  });

  it('only the hub closes with #done', () => {
    const msgs = [
      { seq: 1, from_pubkey: 'hub', body: '#task #cite-cwv Cite?' },
      { seq: 2, from_pubkey: 'peer', body: '#done not the hub' },
      { seq: 3, from_pubkey: 'hub', body: '#done yes' },
    ];
    const tasks = buildTasks(msgs, 'hub');
    expect(tasks).toHaveLength(1);
    expect(tasks[0].status).toBe('done');
  });

  it('a combined #task+#done post is prose — never opens or closes a task', () => {
    const msgs = [
      { seq: 1, from_pubkey: 'hub', body: '#task #live In progress' },
      { seq: 2, from_pubkey: 'hub', body: '#task #other Other\n#done both markers' },
    ];
    const tasks = buildTasks(msgs, 'hub');
    expect(tasks).toHaveLength(1);
    expect(tasks[0].slug).toBe('live');
    expect(tasks[0].status).toBe('working');
  });
});

describe('findBlocked', () => {
  it('flags a #done BLOCKED close as blocked', () => {
    const msgs = [
      { seq: 1, from_pubkey: 'hub', body: '@pixel #task #build wire it' },
      { seq: 2, from_pubkey: 'hub', body: '#done BLOCKED build · deps missing' },
    ];
    expect(findBlocked(msgs, 'hub')).toEqual({ slug: 'build', reason: 'BLOCKED build · deps missing' });
  });

  it('a green close is not blocked', () => {
    const msgs = [
      { seq: 1, from_pubkey: 'hub', body: '#task #qa audit' },
      { seq: 2, from_pubkey: 'hub', body: '#done qa green' },
    ];
    expect(findBlocked(msgs, 'hub')).toBeNull();
  });

  it('a re-task after the block clears the banner', () => {
    const msgs = [
      { seq: 1, from_pubkey: 'hub', body: '#task #build go' },
      { seq: 2, from_pubkey: 'hub', body: '#done BLOCKED build' },
      { seq: 3, from_pubkey: 'hub', body: '@pixel #task #build-recheck retry' },
    ];
    expect(findBlocked(msgs, 'hub')).toBeNull();
  });
});
