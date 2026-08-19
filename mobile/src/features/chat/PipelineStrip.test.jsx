import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { fontOf, h } = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
  h: { onScroll: null },
}));

vi.mock('react-native-svg', () => {
  const El = (tag) => ({ children, ...p }) => React.createElement(tag, {}, children);
  const Svg = El('svg');
  return { default: Svg, Svg, Defs: El('defs'), LinearGradient: El('lineargradient'), Rect: El('rect'), Stop: El('stop') };
});

vi.mock('react-native', () => {
  const plain = ({
    style,
    contentContainerStyle,
    onLayout,
    accessibilityLabel,
    accessibilityHint,
    accessibilityState,
    accessibilityElementsHidden,
    importantForAccessibility,
    ...rest
  }) => ({
    ...rest,
    ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
    ...(accessibilityHint ? { title: accessibilityHint } : {}),
    ...(accessibilityState?.disabled ? { 'aria-disabled': 'true' } : {}),
    ...(accessibilityElementsHidden ? { 'data-a11y-hidden-ios': 'true' } : {}),
    ...(importantForAccessibility ? { 'data-a11y-android': importantForAccessibility } : {}),
    'data-font': fontOf(style),
    ...(rest.testID ? { 'data-testid': rest.testID } : {}),
    'data-style': JSON.stringify(Object.assign({}, ...[style].flat(Infinity).filter(Boolean))),
  });
  const View = ({ children, ...p }) => React.createElement('div', plain(p), children);
  const Text = ({ children, ...p }) => React.createElement('span', plain(p), children);
  const Pressable = ({ children, onPress, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...plain(p) }, children);
  const ScrollView = React.forwardRef(({ children, onScroll, ...p }, ref) =>
    React.createElement('div', {
      ...plain(p), ref, 'data-scroll': 'horizontal',
    }, (h.onScroll = onScroll, children)));
  return { View, Text, Pressable, ScrollView, StyleSheet: { create: (s) => s } };
});

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: {
        ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
        success: '#0a0', warning: '#c80', danger: '#c00',
        line2: '#eee', bgInput: '#fafafa',
      },
      fonts: { sans: { regular: 'Inter_400Regular' }, mono: 'm', monoMedium: 'mm' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../components/Icon', () => ({
  Icon: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));

vi.mock('../../components/Dot', () => ({
  Dot: () => React.createElement('span', { 'data-dot': 'true' }),
}));

vi.mock('../../components/Pill', () => ({
  Pill: ({ tone, off, children }) =>
    React.createElement('span', { 'data-pill': tone ?? (off ? 'off' : '') }, children),
}));

import { PipelineStrip } from './PipelineStrip';

const RUN = {
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
};

const LOADED = new Set([40, 42, 43]);

function strip(run = RUN, props = {}) {
  return render(<PipelineStrip run={run} accent="#f00" loadedSeqs={LOADED} {...props} />);
}

describe('PipelineStrip', () => {
  it('renders nothing without a run', () => {
    const { container } = strip(null);
    expect(container.textContent).toBe('');
  });

  it('renders nothing for a run the daemon sent without phases', () => {
    expect(strip({ pipeline: 'setup', status: 'running' }).container.textContent).toBe('');
    expect(strip({ pipeline: 'setup', status: 'running', phases: [] }).container.textContent).toBe('');
  });

  it("labels the strip as desktop does — pipeline · the run's key, not the launch chain", () => {
    strip();
    expect(screen.getByText('pipeline · media-update')).toBeTruthy();
    expect(screen.getByLabelText('#media-build current')).toBeTruthy();
  });

  it('renders every phase state, skipped distinct from completed', () => {
    strip();
    expect(screen.getByLabelText('#media-update completed')).toBeTruthy();
    expect(screen.getByLabelText('#media-config skipped')).toBeTruthy();
    expect(screen.getByLabelText('#media-qa pending')).toBeTruthy();
    const skipped = screen.getByLabelText('#media-config skipped');
    const completed = screen.getByLabelText('#media-update completed');
    expect(skipped.querySelector('[data-icon="x"]')).toBeTruthy();
    expect(completed.querySelector('[data-icon="check"]')).toBeTruthy();
  });

  it('renders a blocked run with the current phase blocked', () => {
    strip({ ...RUN, status: 'blocked' });
    expect(screen.getByLabelText('#media-build blocked')).toBeTruthy();
    expect(screen.getByLabelText('#media-build blocked').querySelector('[data-icon="ban"]')).toBeTruthy();
  });

  it('separates the phase chain as desktop WorkgroupView does — a chevron in a theme font', () => {
    strip();
    const separators = screen.getAllByText('›');
    expect(separators).toHaveLength(3);
    for (const s of separators) expect(s.getAttribute('data-font')).toBe('Inter_400Regular');
  });

  it('keeps the separator out of the accessibility tree on both platforms, as desktop aria-hides it', () => {
    strip();
    const separators = screen.getAllByText('›');
    expect(separators).toHaveLength(3);
    for (const s of separators) {
      expect(s.getAttribute('data-a11y-hidden-ios')).toBe('true');
      expect(s.getAttribute('data-a11y-android')).toBe('no-hide-descendants');
    }
    const phase = screen.getByLabelText('#media-build current');
    expect(phase.getAttribute('data-a11y-hidden-ios')).toBeNull();
    expect(phase.getAttribute('data-a11y-android')).toBeNull();
  });

  it('jumps to a loaded phase seq and says so', () => {
    const onPickSeq = vi.fn();
    strip(RUN, { onPickSeq });
    const phase = screen.getByLabelText('#media-update completed');
    expect(phase.getAttribute('title')).toBe('Jump to #media-update');
    fireEvent.click(phase);
    expect(onPickSeq).toHaveBeenCalledWith(40);
  });

  it('never offers a jump to a phase that has not opened, and says why', () => {
    strip(RUN, { onPickSeq: vi.fn() });
    const pending = screen.getByLabelText('#media-qa pending');
    expect(pending.tagName).toBe('DIV');
    expect(pending.getAttribute('aria-disabled')).toBe('true');
    expect(pending.getAttribute('title')).toBe('#media-qa has not opened yet — nothing to jump to');
  });

  it('never offers a jump to a seq outside the loaded history, and says where it is', () => {
    strip(RUN, { onPickSeq: vi.fn(), loadedSeqs: new Set([43]) });
    const outside = screen.getByLabelText('#media-update completed');
    expect(outside.tagName).toBe('DIV');
    expect(outside.getAttribute('aria-disabled')).toBe('true');
    expect(outside.getAttribute('title')).toBe('#media-update opened at post #40, outside the loaded history');
    expect(screen.getByLabelText('#media-build current').tagName).toBe('BUTTON');
  });

  it('offers no jump at all when the thread reports no loaded history', () => {
    strip(RUN, { onPickSeq: vi.fn(), loadedSeqs: undefined });
    for (const label of ['#media-update completed', '#media-config skipped', '#media-build current']) {
      expect(screen.getByLabelText(label).tagName).toBe('DIV');
    }
  });

  it('shows the run status desktop shows, and stays silent while a phase is running', () => {
    const pill = (container) => container.querySelector('[data-pill]');
    expect(pill(strip().container)).toBeNull();
    expect(pill(strip({ ...RUN, status: 'between' }).container).textContent).toBe('between phases');
    expect(pill(strip({ ...RUN, status: 'between' }).container).getAttribute('data-pill')).toBe('off');
    expect(pill(strip({ ...RUN, status: 'blocked' }).container).textContent).toBe('blocked');
    expect(pill(strip({ ...RUN, status: 'blocked' }).container).getAttribute('data-pill')).toBe('err');
    expect(pill(strip({ ...RUN, status: 'completed' }).container).textContent).toBe('completed');
    expect(pill(strip({ ...RUN, status: 'completed' }).container).getAttribute('data-pill')).toBe('on');
  });

  it('hides the strip when an ad-hoc task nulls a run that was already on screen', () => {
    const { container, rerender } = strip();
    expect(container.querySelector('[data-testid="strip"]')).toBeTruthy();
    rerender(<PipelineStrip run={null} accent="#f00" loadedSeqs={LOADED} />);
    expect(container.querySelector('[data-testid="strip"]')).toBeNull();
    expect(screen.queryByText('#media-update')).toBeNull();
  });

  it('scrolls the chain sideways rather than wrapping the header onto extra lines', () => {
    const { container } = strip();
    expect(container.querySelector('[data-scroll="horizontal"]')).toBeTruthy();
    const row = JSON.parse(container.querySelector('[data-scroll]').getAttribute('data-style') || '{}');
    expect(row.flexWrap).toBeUndefined();
  });

  it('fades the edge only on the side that actually hides phases', () => {
    const { container } = strip();
    expect(container.querySelectorAll('svg')).toHaveLength(0);

    const frame = (x, content, view) => ({
      nativeEvent: { contentOffset: { x }, contentSize: { width: content }, layoutMeasurement: { width: view } },
    });
    act(() => { h.onScroll(frame(0, 900, 400)); });
    expect(container.querySelectorAll('svg')).toHaveLength(1);

    act(() => { h.onScroll(frame(200, 900, 400)); });
    expect(container.querySelectorAll('svg')).toHaveLength(2);

    act(() => { h.onScroll(frame(500, 900, 400)); });
    expect(container.querySelectorAll('svg')).toHaveLength(1);

    act(() => { h.onScroll(frame(0, 300, 400)); });
    expect(container.querySelectorAll('svg')).toHaveLength(0);
  });

  it('carries no way to start a pipeline — every pressable is a phase jump', () => {
    const { container } = strip(RUN, { onPickSeq: vi.fn() });
    expect([...container.querySelectorAll('button')].map((b) => b.getAttribute('aria-label'))).toEqual([
      '#media-update completed',
      '#media-config skipped',
      '#media-build current',
    ]);
    expect(container.textContent).not.toMatch(/run/i);
  });
});
