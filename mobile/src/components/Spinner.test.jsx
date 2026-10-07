import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { BUSY_LABEL } from '../../../common/busy.mjs';

const h = vi.hoisted(() => ({ reduce: false, timings: [], started: 0, stopped: 0, interpolations: 0 }));

vi.mock('react-native', () => {
  class Value {
    setValue() {}
    interpolate({ outputRange }) { h.interpolations += 1; return outputRange.join('→'); }
  }
  const Animated = {
    Value,
    View: ({ children, style, accessibilityRole, accessibilityLabel, accessible, ...p }) =>
      React.createElement('div', { ...p, role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-rotate': String(style.transform[0].rotate), 'data-size': style.width }, children),
    timing: (value, config) => { h.timings.push(config); return {}; },
    loop: () => ({ start: () => { h.started += 1; }, stop: () => { h.stopped += 1; } }),
  };
  return { Animated, Easing: { linear: 'linear' } };
});
vi.mock('../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { ink2: '#333333', ink3: '#666666' } }) }));

const { Spinner, SPINNER_SIZE } = await import('./Spinner');

beforeEach(() => Object.assign(h, { reduce: false, timings: [], started: 0, stopped: 0, interpolations: 0 }));
afterEach(cleanup);

describe('Spinner', () => {
  it('draws one open arc in the second ink at the size a platform indicator had', () => {
    const { container } = render(<Spinner />);
    const path = container.querySelector('path');
    expect(container.querySelectorAll('path')).toHaveLength(1);
    expect(path.getAttribute('stroke')).toBe('#333333');
    expect(path.getAttribute('fill')).toBeNull();
    expect(container.querySelector('[role="progressbar"]').dataset.size).toBe(String(SPINNER_SIZE));
    expect(SPINNER_SIZE).toBe(20);
  });

  it('takes the ink of the control it sits in', () => {
    const { container } = render(<Spinner color="#ffffff" size={14} />);
    expect(container.querySelector('path').getAttribute('stroke')).toBe('#ffffff');
    expect(container.querySelector('svg').getAttribute('width')).toBe('14');
  });

  it('turns in a linear loop and is labelled Loading', () => {
    const { container } = render(<Spinner />);
    expect(h.started).toBe(1);
    expect(h.timings[0]).toMatchObject({ toValue: 1, easing: 'linear', useNativeDriver: true });
    expect(container.querySelector('[role="progressbar"]').getAttribute('aria-label')).toBe(BUSY_LABEL);
    expect(container.querySelector('[role="progressbar"]').dataset.rotate).toBe('0deg→360deg');
  });

  it('builds its rotation once, not on every render', () => {
    const view = render(<Spinner color="#111111" />);
    view.rerender(<Spinner color="#222222" />);
    view.rerender(<Spinner color="#333333" />);
    expect(h.interpolations).toBe(1);
  });

  it('holds still under reduced motion', () => {
    h.reduce = true;
    const { container } = render(<Spinner />);
    expect(h.started).toBe(0);
    expect(container.querySelector('[role="progressbar"]').dataset.rotate).toBe('0deg');
  });

  it('stops turning when it leaves', () => {
    render(<Spinner />).unmount();
    expect(h.stopped).toBe(1);
  });
});
