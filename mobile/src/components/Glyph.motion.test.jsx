import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { STILL } from '../../../common/agentMarks.mjs';
import { state as anim } from '../../tests/mocks/reanimated.js';

afterEach(() => {
  cleanup();
  anim.timings.length = 0;
});

vi.mock('react-native', () => {
  const View = ({ children, style, pointerEvents, ...p }) => React.createElement('div', p, children);
  return { View };
});

vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => false }));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink3: '#828b97' }, mode: 'light' }),
}));

const { Glyph } = await import('./Glyph');

const ROWS = [
  { rowState: 'working' },
  { pending: true },
  { rowState: 'needs-you' },
  { needsProvider: true },
  { unread: true },
  { rowState: 'failed' },
];

describe('roster motion', () => {
  it('runs no live loop for a roster of busy rows that are not selected, and still draws each state', () => {
    const { container } = render(
      <>
        {ROWS.map((row, i) => <Glyph key={i} kind="profile" shape="bell" color="#3899e2" name={`p${i}`} {...row} />)}
        <Glyph kind="workgroup" color="#3899e2" working phase="1/3" />
      </>,
    );
    expect(anim.timings).toHaveLength(0);
    const states = [...container.querySelectorAll('[data-mark]')].map((el) => el.getAttribute('data-state'));
    expect(states).toEqual(['working', 'working', 'needs', 'needs', 'done', 'failed', 'running']);
    expect(Object.keys(STILL)).toEqual(expect.arrayContaining(['working', 'needs', 'done', 'failed']));
  });

  it('animates only the selected row', () => {
    render(
      <>
        <Glyph kind="profile" shape="bell" color="#3899e2" name="a" rowState="working" />
        <Glyph kind="profile" shape="heart" color="#3899e2" name="b" rowState="working" active />
        <Glyph kind="profile" shape="pill" color="#3899e2" name="c" rowState="needs-you" />
      </>,
    );
    expect(anim.timings).toHaveLength(1);
  });

  it('keeps the selected row live and the others still when the selection moves', () => {
    const roster = (selected) => ['a', 'b', 'c'].map((name) => (
      <Glyph key={name} kind="profile" shape="bell" color="#3899e2" name={name} rowState="failed" active={name === selected} />
    ));
    const view = render(<>{roster('a')}</>);
    expect(anim.timings).toHaveLength(1);
    anim.timings.length = 0;
    view.rerender(<>{roster(null)}</>);
    expect(anim.timings).toHaveLength(0);
  });
});
