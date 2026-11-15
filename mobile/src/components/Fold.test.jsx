import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

import { BRAND_INK, SHAPE_IDS } from '../../../common/shapes.mjs';
import { LEGACY_SHAPE, SHAPES, TURN } from '../../../common/agentMarks.mjs';
import { WG_ALPHA } from '../../../common/workgroupMark.mjs';
import { ACCENT_HEXES } from '../../../common/accents.mjs';
import { contrastRatio, nameTone } from '../../../common/name.mjs';
import { palettes } from '../../../common/tokens.mjs';

const INK3 = '#828b97';
import { state as anim } from '../../tests/mocks/reanimated.js';

const h = vi.hoisted(() => ({ mode: 'light', reduce: false, app: 'active', appListeners: new Set(), bg: undefined }));

afterEach(() => {
  cleanup();
  h.reduce = false;
  h.mode = 'light';
  h.app = 'active';
  h.bg = undefined;
  anim.timings.length = 0;
});

vi.mock('react-native', () => {
  const View = ({ children, style, pointerEvents, ...p }) => React.createElement('div', { ...p, 'data-style': JSON.stringify(style ?? null) }, children);
  const AppState = {
    get currentState() { return h.app; },
    addEventListener: (_, fn) => {
      h.appListeners.add(fn);
      return { remove: () => h.appListeners.delete(fn) };
    },
  };
  return { View, AppState };
});

vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink3: '#828b97', danger: '#c14545', accent: '#14110c', bg: h.bg, markEye: palettes[h.mode].markEye }, mode: h.mode }),
}));

const { Fold } = await import('./Fold');

const draw = (props) => render(<Fold {...props} />).container;
const slot = (root) => root.querySelector('[data-mark]');
const turnOf = (root) => {
  const turned = [...root.querySelectorAll('[data-style]')].map((el) => JSON.parse(el.getAttribute('data-style'))).find((s) => s && Array.isArray(s.transform));
  return turned.transform.slice(1).map((t) => parseFloat(Object.values(t)[0]));
};
const loops = () => anim.timings.length;
const attr = (el, name) => el.getAttribute(name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)) ?? el.getAttribute(name);

describe('Fold profile marks', () => {
  it.each(SHAPE_IDS)('draws the shape %s in the profile colour with two filled eyes over it', (name) => {
    const root = draw({ shape: name, color: '#3899e2', state: 'idle' });
    expect(slot(root).getAttribute('data-mark')).toBe(name);
    expect(slot(root).getAttribute('data-shape')).toBe(name);
    const [body, eyes] = root.querySelectorAll('path');
    expect(body.getAttribute('fill')).toBe('#3899e2');
    expect(attr(body, 'fillRule')).toBeNull();
    expect(body.getAttribute('d')).toBe(SHAPES[name].d);
    expect(eyes.getAttribute('fill')).toBe('#ffffff');
    expect(eyes.getAttribute('d').match(/M/g)).toHaveLength(2);
  });

  it.each([['light', '#ffffff'], ['dark', '#000000']])('fills the eyes white in light and black in dark, still and live (%s)', (mode, ink) => {
    h.mode = mode;
    for (const props of [{ size: 24, state: 'idle' }, { size: 72, state: 'working' }]) {
      const root = draw({ shape: 'bell', color: '#3899e2', ...props });
      const paths = root.querySelectorAll('path');
      expect(paths).toHaveLength(2);
      expect(paths[1].getAttribute('fill')).toBe(ink);
      cleanup();
    }
  });

  it.each([['light', '#ec6a88'], ['dark', '#f36a8a']])('draws a pale accent a step deeper in light so the white eyes hold 3:1, as stored in dark (%s)', (mode, tone) => {
    h.mode = mode;
    for (const props of [{ size: 24, state: 'idle' }, { size: 72, state: 'working' }, { size: 24, state: 'offline' }]) {
      const body = draw({ shape: 'heart', color: '#f36a8a', ...props }).querySelector('path');
      expect(body.getAttribute('fill')).toBe(tone);
      cleanup();
    }
  });

  it('draws an unknown or missing shape as the round mark', () => {
    for (const shape of [undefined, null, '', 'pencil', 'shield', 'rocket', 'alpaca']) {
      expect(slot(draw({ shape, color: '#3899e2' })).getAttribute('data-mark'), String(shape)).toBe('round');
      cleanup();
    }
  });

  it.each(['light', 'dark'])('draws the default profile as Twin in the %s brand ink, never its accent', (mode) => {
    h.mode = mode;
    const root = draw({ shape: 'twin', color: '#f0b447', size: 72, state: 'idle' });
    expect(slot(root).getAttribute('data-mark')).toBe('alpi-twin');
    expect(root.querySelector('path').getAttribute('fill')).toBe(BRAND_INK[mode]);
    expect(root.innerHTML).not.toContain('#f0b447');
  });

  it('switches Twin to its small variant under 24 px', () => {
    expect(slot(draw({ shape: 'twin', size: 20 })).getAttribute('data-mark')).toBe('alpi-twin-small');
    cleanup();
    expect(slot(draw({ shape: 'twin', size: 24 })).getAttribute('data-mark')).toBe('alpi-twin');
    cleanup();
    expect(slot(draw({ shape: 'alpaca', size: 24 })).getAttribute('data-mark')).toBe('round');
  });

  it('sizes rows at 24, headers at 28 and pixel sizes as given', () => {
    expect(draw({ shape: 'heart', color: '#f36a8a' }).querySelector('svg').getAttribute('width')).toBe('24');
    cleanup();
    expect(draw({ shape: 'heart', color: '#f36a8a', size: 'md' }).querySelector('svg').getAttribute('width')).toBe('28');
    cleanup();
    expect(draw({ shape: 'heart', color: '#f36a8a', size: 40 }).querySelector('svg').getAttribute('width')).toBe('40');
  });

  it('draws in neutral grey when the colour is not a hex', () => {
    const root = draw({ shape: 'pebble', color: 'var(--accent)' });
    expect(root.querySelector('path').getAttribute('fill')).toBe('#828b97');
  });

  it.each([
    ['paused', { state: 'paused' }],
    ['unfolded', { unfolded: true, pulse: true }],
  ])('draws %s as a dashed neutral outline with no fill and no motion', (_, props) => {
    const root = draw({ shape: 'bell', color: '#3899e2', size: 72, ...props });
    const [outline, eyes] = root.querySelectorAll('path');
    expect(outline.getAttribute('fill')).toBe('none');
    expect(outline.getAttribute('stroke')).toBe('#828b97');
    expect(attr(outline, 'strokeDasharray')).toBeTruthy();
    expect(eyes.getAttribute('fill')).toBe('#828b97');
    expect(root.innerHTML).not.toContain('#3899e2');
    expect(turnOf(root)).toEqual([0, 0, 0]);
    expect(loops()).toBe(0);
  });

  it('reads the old outlined flag as needs, never a disabled look', () => {
    const root = draw({ shape: 'bell', color: '#3899e2', size: 72, outlined: true });
    expect(slot(root).getAttribute('data-state')).toBe('needs');
    expect(root.querySelector('path').getAttribute('fill')).toBe('#3899e2');
    expect(slot(draw({ shape: 'bell', color: '#3899e2', state: 'disabled' })).getAttribute('data-state')).toBe('idle');
  });

  it('holds the still form of any state when asked to stay still', () => {
    for (const state of ['busy', 'working', 'needs', 'done', 'failed']) {
      const root = draw({ shape: 'bell', color: '#3899e2', size: 72, state, still: true });
      expect(slot(root).getAttribute('data-state')).toBe(state);
      expect(turnOf(root)).toEqual(TURN.still[state]);
      cleanup();
    }
    draw({ shape: 'honeycomb', color: '#3899e2', state: 'running', phase: '2/3', size: 'md', still: true });
    expect(loops()).toBe(0);
  });

  it('fades an offline mark to 30 % with no eyes, frontal and still', () => {
    const root = draw({ shape: 'squircle', color: '#3899e2', size: 72, state: 'offline' });
    const path = root.querySelector('path');
    expect(path.getAttribute('d')).toBe(SHAPES.squircle.d);
    expect(attr(path, 'fillOpacity')).toBe('0.3');
    expect(turnOf(root)).toEqual([0, 0, 0]);
    expect(loops()).toBe(0);
  });

  it('holds the turned pose at rest and halves it at row size', () => {
    h.reduce = true;
    expect(turnOf(draw({ shape: 'clover', color: '#3899e2', size: 72, state: 'idle' }))).toEqual(TURN.still.idle);
    cleanup();
    expect(turnOf(draw({ shape: 'clover', color: '#3899e2', state: 'idle' }))).toEqual(TURN.still.idle.map((a) => a * TURN.smallTurn));
  });

  it('keeps an idle row mark still so a roster runs no loops', () => {
    for (let i = 0; i < 30; i += 1) draw({ shape: SHAPE_IDS[i % SHAPE_IDS.length], color: '#3899e2', state: 'idle' });
    expect(loops()).toBe(0);
  });

  it('morphs the eyes of a working row mark but keeps its turn fixed', () => {
    const root = draw({ shape: 'pill', color: '#3899e2', state: 'working' });
    expect(loops()).toBe(1);
    expect(turnOf(root)).toEqual(TURN.still.working.map((a) => a * TURN.smallTurn));
  });

  it('stops every live loop while the app is in the background and resumes when it is active again', () => {
    const background = (next) => act(() => {
      h.app = next;
      for (const fn of [...h.appListeners]) fn(next);
    });
    const { container, unmount } = render(
      <>
        <Fold shape="bell" color="#3899e2" size={72} state="working" />
        <Fold shape="honeycomb" color="#3899e2" size={72} state="running" phase="2/3" />
      </>,
    );
    expect(loops()).toBe(2);
    expect(h.appListeners.size).toBe(1);
    anim.timings.length = 0;
    background('background');
    expect(loops()).toBe(0);
    expect(container.querySelector('[data-state="working"]')).not.toBeNull();
    expect(turnOf(container)).toEqual(TURN.still.working);
    background('inactive');
    expect(loops()).toBe(0);
    background('active');
    expect(loops()).toBe(2);
    unmount();
    expect(h.appListeners.size).toBe(0);
  });

  it('starts still when the app is already in the background', () => {
    h.app = 'background';
    draw({ shape: 'bell', color: '#3899e2', size: 72, state: 'needs' });
    expect(loops()).toBe(0);
  });

  it('turns a busy mark live above row size on one clock', () => {
    draw({ shape: 'twin', size: 40, state: 'busy' });
    expect(loops()).toBe(1);
    expect(anim.timings[0].duration).toBe(8400);
  });

  it('maps pulse to working', () => {
    expect(slot(draw({ shape: 'bell', color: '#3899e2', pulse: true })).getAttribute('data-state')).toBe('working');
  });

  it('shows the still expression with no motion under reduced motion', () => {
    h.reduce = true;
    const root = draw({ shape: 'bell', color: '#3899e2', size: 72, state: 'busy' });
    expect(loops()).toBe(0);
    expect(turnOf(root)).toEqual(TURN.still.busy);
  });

  it('does not animate below the motion floor', () => {
    draw({ shape: 'bell', color: '#3899e2', size: 14, state: 'working' });
    expect(loops()).toBe(0);
  });
});

describe('Fold workgroup honeycomb', () => {
  const fills = (root) => [...root.querySelectorAll('path')].map((p) => [p.getAttribute('fill'), attr(p, 'fillOpacity')]);

  const strokes = (root) => [...root.querySelectorAll('path')].map((p) => p.getAttribute('stroke'));

  it('draws three soft cells in neutral ink at rest, never the hub colour', () => {
    const root = draw({ shape: 'honeycomb', color: '#3899e2', size: 'md' });
    expect(slot(root).getAttribute('data-mark')).toBe('soft-honeycomb');
    expect(fills(root)).toEqual([[INK3, null], [INK3, null], [INK3, null]]);
  });

  it('keeps done neutral and outlines queued in neutral ink', () => {
    expect(fills(draw({ shape: 'honeycomb', color: '#3899e2', state: 'done' }))).toEqual([[INK3, null], [INK3, null], [INK3, null]]);
    cleanup();
    const queued = draw({ shape: 'honeycomb', color: '#3899e2', state: 'queued' });
    expect(fills(queued).map(([f]) => f)).toEqual(['none', 'none', 'none']);
    expect(strokes(queued)).toEqual([INK3, INK3, INK3]);
  });

  it('lights only the current phase cell in the hub colour, finished cells faint neutral, pending outlined, never an owner colour', () => {
    h.reduce = true;
    const root = draw({ shape: 'honeycomb', color: '#3899e2', state: 'running', phase: '1/3', active: '#e2558a' });
    expect(fills(root)).toEqual([[INK3, String(WG_ALPHA.faint)], ['#3899e2', null], ['none', null]]);
    expect(strokes(root)[2]).toBe(INK3);
    expect(root.innerHTML).not.toContain('#e2558a');
  });

  it('fills only the waiting cell in the hub colour when it needs you, the rest neutral, never an owner colour', () => {
    h.reduce = true;
    const root = draw({ shape: 'honeycomb', color: '#3899e2', state: 'needs', phase: '2/3' });
    expect(fills(root).filter(([fill]) => fill === '#3899e2')).toHaveLength(1);
    expect(fills(root).filter(([fill]) => fill === INK3)).toHaveLength(2);
  });

  it.each(ACCENT_HEXES)('lights %s in its name tone on the theme ground, at 3:1 or more in both themes', (accent) => {
    h.reduce = true;
    for (const mode of ['light', 'dark']) {
      h.bg = palettes[mode].bg;
      const tone = nameTone(accent, h.bg);
      for (const props of [{ state: 'running', phase: '1/3' }, { state: 'needs', phase: '1/3' }, { state: 'running' }]) {
        const lit = fills(draw({ shape: 'honeycomb', color: accent, size: 40, ...props })).filter(([fill]) => fill === tone);
        expect(lit.length, `${mode} ${props.state}`).toBeGreaterThan(0);
        cleanup();
      }
      expect(contrastRatio(tone, palettes[mode].bg)).toBeGreaterThanOrEqual(3);
    }
  });

  it('treats a malformed phase array as a run without counts', () => {
    h.reduce = true;
    for (const phase of [[], [1, 0], [null, 3]]) {
      const root = draw({ shape: 'honeycomb', color: '#3899e2', state: 'running', phase });
      expect(fills(root).map(([fill]) => fill)).toEqual(['#3899e2', '#3899e2', '#3899e2']);
      cleanup();
    }
  });

  it('pops the waiting cell above row size, header included, and fills it flat at row size', () => {
    h.reduce = true;
    expect(draw({ shape: 'honeycomb', color: '#3899e2', state: 'needs', phase: '1/3', size: 'md' }).querySelector('g[transform]')).not.toBeNull();
    cleanup();
    expect(draw({ shape: 'honeycomb', color: '#3899e2', state: 'needs', phase: '1/3', size: 20 }).querySelector('g[transform]')).toBeNull();
  });

  it('fills the failed cell in the danger colour, the rest faint neutral', () => {
    h.reduce = true;
    const root = draw({ shape: 'honeycomb', color: '#3899e2', state: 'failed', cell: 'left' });
    expect(fills(root)).toEqual([['#c14545', null], [INK3, String(WG_ALPHA.faint)], [INK3, String(WG_ALPHA.faint)]]);
  });

  it('leans the active cell toward the viewer, half as far at row size', () => {
    h.reduce = true;
    expect(turnOf(draw({ shape: 'honeycomb', color: '#3899e2', state: 'running', phase: '0/3' }))).toEqual([13, 3, -0.75]);
  });

  it('turns live above row size and stays still in rows', () => {
    draw({ shape: 'honeycomb', color: '#3899e2', state: 'running', phase: '2/3', size: 'md' });
    expect(loops()).toBe(1);
    anim.timings.length = 0;
    cleanup();
    draw({ shape: 'honeycomb', color: '#3899e2', state: 'running', phase: '2/3' });
    expect(loops()).toBe(0);
  });

  it('draws a paused, unfolded or outlined honeycomb as a dashed neutral outline, frontal', () => {
    for (const props of [{ state: 'paused' }, { unfolded: true }, { outlined: true }]) {
      const root = draw({ shape: 'honeycomb', color: '#3899e2', size: 'md', ...props });
      for (const path of root.querySelectorAll('path')) {
        expect(path.getAttribute('fill')).toBe('none');
        expect(path.getAttribute('stroke')).toBe('#828b97');
        expect(attr(path, 'strokeDasharray')).toBeTruthy();
      }
      expect(turnOf(root)).toEqual([0, 0, 0]);
      cleanup();
    }
    expect(loops()).toBe(0);
  });

  it('fades an offline honeycomb in neutral ink', () => {
    const root = draw({ shape: 'honeycomb', color: '#3899e2', state: 'offline' });
    expect(fills(root).every(([f, o]) => f === INK3 && o === String(WG_ALPHA.offline))).toBe(true);
  });
});
