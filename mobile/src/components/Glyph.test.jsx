import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { MARK_SIZES } from '../../../common/agentMarks.mjs';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, pointerEvents, ...p }) => React.createElement('div', p, children);
  return { View };
});

vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => true }));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink3: '#828b97' }, mode: 'light' }),
}));

const { Glyph, markState, workgroupGlyph } = await import('./Glyph');

const mark = (glyph) => render(glyph).container.querySelector('[data-mark]');

describe('markState', () => {
  it.each([
    [{}, 'idle'],
    [{ unread: true }, 'done'],
    [{ pending: true, unread: true }, 'working'],
    [{ pending: true }, 'working'],
    [{ working: true, pending: true }, 'working'],
    [{ rowState: 'working' }, 'working'],
    [{ rowState: 'failed', working: true }, 'failed'],
    [{ rowState: 'needs-you', working: true }, 'needs'],
    [{ paused: true, rowState: 'needs-you' }, 'paused'],
    [{ needsProvider: true }, 'needs'],
    [{ needsProvider: true, working: true }, 'needs'],
    [{ needsProvider: true, paused: true }, 'paused'],
    [{ offline: true, needsProvider: true }, 'offline'],
  ])('maps %o to %s', (row, state) => {
    expect(markState(row)).toBe(state);
  });

  it('maps a workgroup row to the honeycomb states the desktop shows', () => {
    const state = (row) => workgroupGlyph(row).state;
    expect(state({ working: true })).toBe('running');
    expect(state({ rowState: 'working' })).toBe('running');
    expect(state({ working: true, paused: true })).toBe('paused');
    expect(state({ offline: true })).toBe('offline');
    expect(state({ workgroup: { pipeline_status: 'blocked' } })).toBe('needs');
    expect(state({ workgroup: { pipeline_status: 'queued' } })).toBe('queued');
    expect(state({ rowState: 'failed' })).toBe('failed');
    expect(state({ workgroup: { pipeline_status: 'running' } })).toBe('running');
    expect(state({})).toBe('idle');
  });

  it('names the owner of the current phase and hands the mark no colour of its own', () => {
    const workgroup = { pipeline_status: 'running', phase_map: { translate: { owner: '@Scout' } } };
    const mark = workgroupGlyph({ workgroup, rowState: 'working', phase: '1/3', phaseSlug: 'translate' });
    expect(mark).toEqual({ state: 'running', phase: [1, 3], step: 'translate', owner: 'Scout' });
    expect(workgroupGlyph({ workgroup: { ...workgroup, pipeline_status: 'blocked', pipeline_phase: 'translate' } }).owner).toBe('Scout');
    expect(workgroupGlyph({ workgroup, rowState: 'working', phaseSlug: 'file' }).owner).toBeNull();
  });
});

describe('Glyph', () => {
  it('draws a profile as its mark in its colour at the shared row size', () => {
    const slot = mark(<Glyph kind="profile" shape="bell" color="#3899e2" />);
    expect(slot.getAttribute('data-mark')).toBe('bell');
    cleanup();
    expect(mark(<Glyph kind="profile" shape="shield" color="#3899e2" />).getAttribute('data-mark')).toBe('round');
    cleanup();
    expect(slot.querySelector('path').getAttribute('fill')).toBe('#3899e2');
    expect(slot.getAttribute('width')).toBe(String(MARK_SIZES.row));
  });

  it('carries the row state onto the mark', () => {
    expect(mark(<Glyph kind="profile" shape="heart" color="#3899e2" rowState="needs-you" />).getAttribute('data-state')).toBe('needs');
    cleanup();
    expect(mark(<Glyph kind="profile" shape="heart" color="#3899e2" needsProvider working />).getAttribute('data-state')).toBe('needs');
    cleanup();
    expect(mark(<Glyph kind="profile" shape="heart" color="#3899e2" rowState="failed" state="done" />).getAttribute('data-state')).toBe('done');
  });

  it('merges the selected row: an idle session never hides the roster state', () => {
    const state = (props) => {
      const value = mark(<Glyph kind="profile" shape="heart" color="#3899e2" active {...props} />).getAttribute('data-state');
      cleanup();
      return value;
    };
    expect(state({ state: 'idle', rowState: 'failed' })).toBe('failed');
    expect(state({ state: 'idle', working: true })).toBe('working');
    expect(state({ state: 'idle', rowState: 'needs-you' })).toBe('needs');
    expect(state({ state: 'idle', needsProvider: true })).toBe('needs');
    expect(state({ state: 'idle', paused: true })).toBe('paused');
    expect(state({ state: 'idle', unread: true })).toBe('done');
    expect(state({ state: 'idle' })).toBe('idle');
  });

  it('puts paused and a missing provider over the session, and needs you over its done or failed', () => {
    const state = (props) => {
      const value = mark(<Glyph kind="profile" shape="heart" color="#3899e2" active {...props} />).getAttribute('data-state');
      cleanup();
      return value;
    };
    expect(state({ state: 'working', paused: true })).toBe('paused');
    expect(state({ state: 'done', needsProvider: true })).toBe('needs');
    expect(state({ state: 'done', rowState: 'needs-you' })).toBe('needs');
    expect(state({ state: 'failed', rowState: 'needs-you' })).toBe('needs');
    expect(state({ state: 'working', rowState: 'failed' })).toBe('working');
    expect(state({ state: 'failed', working: true })).toBe('failed');
  });

  it('draws a workgroup as the soft honeycomb whatever the shape, only its current cell in the hub colour', () => {
    const workgroup = { phase_map: { translate: { owner: '@scout' } } };
    const slot = mark(<Glyph kind="workgroup" shape="shield" color="#3899e2" working phase="1/3" phaseSlug="translate" workgroup={workgroup} />);
    expect(slot.getAttribute('data-mark')).toBe('soft-honeycomb');
    expect(slot.getAttribute('data-state')).toBe('running');
    const fills = [...slot.querySelectorAll('path')].map((p) => p.getAttribute('fill'));
    expect(fills[1]).toBe('#3899e2');
    expect(fills.filter((f) => f === '#3899e2')).toHaveLength(1);
  });

  it('shows a blocked workgroup as needing you on the phone too', () => {
    expect(mark(<Glyph kind="workgroup" color="#3899e2" workgroup={{ pipeline_status: 'blocked' }} />).getAttribute('data-state')).toBe('needs');
  });

  it('draws a paused workgroup and a paused profile as a grey dashed outline', () => {
    for (const glyph of [<Glyph kind="workgroup" color="#3899e2" paused />, <Glyph kind="profile" shape="heart" color="#3899e2" paused />]) {
      const path = render(glyph).container.querySelector('path');
      expect(path.getAttribute('fill')).toBe('none');
      expect(path.getAttribute('stroke')).toBe('#828b97');
      cleanup();
    }
  });
});
