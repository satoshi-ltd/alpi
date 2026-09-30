import { describe, expect, it } from 'vitest';

import {
  failureLine,
  fmtToolDuration,
  prettyArgs,
  toolCommand,
  toolFamily,
  toolOutput,
  toolSummary,
  toolTitle,
} from './toolDetail';

describe('toolFamily', () => {
  it.each([
    ['read_file', 'file'],
    ['write_file', 'file'],
    ['edit_file', 'file'],
    ['list_dir', 'file'],
    ['terminal', 'terminal'],
    ['shell', 'terminal'],
    ['run', 'terminal'],
    ['web_fetch', 'globe'],
    ['web_search', 'globe'],
    ['browser', 'globe'],
    ['grep', 'search'],
    ['search', 'search'],
    ['session_search', 'search'],
    ['find', 'search'],
    ['peer', 'link'],
    ['send_message', 'link'],
    ['notify', 'link'],
    ['memory', 'brain'],
    ['todo', 'cpu'],
    [undefined, 'cpu'],
  ])('%s → %s', (name, icon) => {
    expect(toolFamily(name)).toBe(icon);
  });
});

describe('tool summaries', () => {
  it('prefers the command, then the path, in plain words', () => {
    expect(toolSummary({ command: 'npm run lint --fix', timeout: 30 })).toBe('npm run lint --fix');
    expect(toolSummary({ path: 'deploy.log', limit: 200 })).toBe('deploy.log');
    expect(toolSummary('{"query":"alpi release"}')).toBe('alpi release');
  });

  it('reads the command from stored JSON args', () => {
    expect(toolCommand('{"command":"ls -la"}')).toBe('ls -la');
    expect(toolCommand({ path: 'a' })).toBeNull();
  });

  it('pretty-prints args as indented JSON', () => {
    expect(prettyArgs({ a: 1, b: 'x' })).toBe('{\n  "a": 1,\n  "b": "x"\n}');
    expect(prettyArgs('{"a":1}')).toBe('{\n  "a": 1\n}');
    expect(prettyArgs(null)).toBe('');
  });
});

describe('tool output', () => {
  it('uses the live output before the stored result and marks truncation', () => {
    expect(toolOutput({ output: 'live', result: 'stored' })).toEqual({ text: 'live', excerpt: false });
    expect(toolOutput({ result: 'stored' })).toEqual({ text: 'stored', excerpt: false });
    expect(toolOutput({ result: `${'x'.repeat(399)}…` }).excerpt).toBe(true);
    expect(toolOutput({})).toEqual({ text: '', excerpt: false });
  });

  it('titles a failure with its duration and shows the first output line inline', () => {
    const t = { name: 'shell', duration_s: 4.1, result: '\nsrc/app.ts:14 no-unused-vars\n1 error' };
    expect(toolTitle(t, 'error')).toBe('shell · failed in 4.1s');
    expect(toolTitle({ name: 'read_file', duration_s: 0.25 }, 'success')).toBe('read_file · 0.3s');
    expect(toolTitle({ name: 'x' }, 'running')).toBe('x · running');
    expect(failureLine(t)).toBe('src/app.ts:14 no-unused-vars');
    expect(failureLine({})).toBe('failed');
  });

  it('formats durations for the sheet title', () => {
    expect(fmtToolDuration(0)).toBe('');
    expect(fmtToolDuration(12.4)).toBe('12s');
    expect(fmtToolDuration(125)).toBe('2m 5s');
  });
});
