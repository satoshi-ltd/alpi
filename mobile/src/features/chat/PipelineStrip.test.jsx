import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

import { phaseGround } from '../../../../common/pipelinePhases.mjs';

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
        success: '#0a0', warning: '#c80', danger: '#c00', dangerText: '#a00',
        line2: '#eee', bgInput: '#fafafa', hover: '#f4f4f4', selected: '#eaeaea',
      },
      fonts: { sans: { regular: 'Geist_400Regular' }, mono: 'm', monoMedium: 'mm', monoSemibold: 'ms' },
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

vi.mock('../../components/Fold', () => ({
  Fold: ({ fold, unfolded, pulse }) => React.createElement('span', { 'data-fold': fold, 'data-unfolded': String(!!unfolded), 'data-pulse': String(!!pulse) }),
}));

vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, subtitle, primaryAction, children }) => (open
    ? React.createElement('section', { 'data-sheet': title, 'data-subtitle': subtitle }, [
      children,
      primaryAction ? React.createElement('button', { key: 'p', type: 'button', onClick: primaryAction.onPress }, primaryAction.label) : null,
    ])
    : null),
}));

import { PipelineStrip, centreOffset } from './PipelineStrip';

const RUN = {
  pipeline: 'media-update',
  status: 'running',
  started_seq: 37,
  current_phase: 'media-build',
  phases: [
    { slug: 'media-update', state: 'completed', seq: 40, cost: { usd: 0.02, tokens: 8310 } },
    { slug: 'media-config', state: 'skipped', seq: 42 },
    { slug: 'media-build', state: 'current', seq: 43 },
    { slug: 'media-qa', state: 'pending', seq: null },
  ],
};

const PHASE_MAP = {
  'media-update': { owner: 'muse', task: 'map the supplied media' },
  'media-build': { owner: 'pixel', task: 'rebuild the site' },
  'media-qa': { owner: 'lens' },
};
const CREW = { muse: { fold: 'star', accent: '#70f' }, pixel: { fold: 'rocket', accent: '#099' }, lingua: { fold: 'plane', accent: '#b29' } };
const profileOf = (name) => CREW[name] ?? null;
const LOADED = new Set([40, 42, 43]);

function strip(run = RUN, props = {}) {
  return render(<PipelineStrip run={run} phaseMap={PHASE_MAP} profileOf={profileOf} loadedSeqs={LOADED} {...props} />);
}

function sheet() {
  return document.querySelector('[data-sheet]');
}

describe('PipelineStrip', () => {
  it('renders nothing without a run or without phases', () => {
    expect(strip(null).container.textContent).toBe('');
    expect(strip({ pipeline: 'setup', status: 'running' }).container.textContent).toBe('');
    expect(strip({ pipeline: 'setup', status: 'running', phases: [] }).container.textContent).toBe('');
  });

  it('marks every phase with its declared owner and its state as its ground, with no check and no word', () => {
    const { container } = strip();
    const ground = (label) => JSON.parse(screen.getByLabelText(label).dataset.style).backgroundColor;
    expect(screen.getByLabelText('#media-build · @pixel · running').querySelector('[data-fold="rocket"]')).toBeTruthy();
    expect(screen.getByLabelText('#media-config · skipped').querySelector('[data-fold]')).toBeNull();
    expect(screen.getByLabelText('#media-qa · @lens · pending').querySelector('[data-unfolded="true"]')).toBeTruthy();
    expect(container.querySelector('[data-icon="check"]')).toBeNull();
    expect(screen.getByLabelText('#media-update · @muse · completed').textContent).toBe('#media-update');
    expect(screen.getByLabelText('#media-build · @pixel · running').textContent).toBe('#media-build');
    expect(ground('#media-update · @muse · completed')).toBe(phaseGround('completed', { success: '#0a0' }));
    expect(ground('#media-build · @pixel · running')).toBe('#eaeaea');
    expect(ground('#media-qa · @lens · pending')).toBe('#f4f4f4');
  });

  it('keeps only steps even when the chain has scrolled off the left edge', () => {
    strip();
    const frame = (x, content, view) => ({
      nativeEvent: { contentOffset: { x }, contentSize: { width: content }, layoutMeasurement: { width: view } },
    });
    expect(screen.queryByText('pipeline · media-update')).toBeNull();
    expect(screen.queryByTestId('pipeline-name')).toBeNull();
    act(() => { h.onScroll(frame(200, 900, 400)); });
    expect(screen.queryByTestId('pipeline-name')).toBeNull();
    act(() => { h.onScroll(frame(0, 900, 400)); });
    expect(screen.queryByTestId('pipeline-name')).toBeNull();
  });

  it('marks a blocked run on its phase, on a red ground, with no run pill', () => {
    const { container } = strip({ ...RUN, status: 'blocked' });
    const blocked = screen.getByLabelText('#media-build · @pixel · blocked');
    expect(JSON.parse(blocked.dataset.style).backgroundColor).toBe(phaseGround('blocked', { danger: '#c00' }));
    expect(blocked.textContent).toBe('#media-build');
    expect(container.querySelector('[data-pill]')).toBeNull();
  });

  it('names the member a routed repair is addressed to, who ripples instead of the owner', () => {
    strip(RUN, { active: { slug: 'media-build', assignees: ['pixel', 'lingua'] } });
    const chip = screen.getByLabelText('#media-build · @pixel · → @lingua · running');
    expect(chip.querySelector('[data-fold="plane"]').getAttribute('data-pulse')).toBe('true');
    expect(chip.querySelector('[data-fold="rocket"]').getAttribute('data-pulse')).toBe('false');
  });

  it('gives every phase a 44 px target that opens its detail', () => {
    strip();
    for (const chip of screen.getAllByRole('button')) {
      expect(JSON.parse(chip.getAttribute('data-style')).minHeight).toBe(44);
    }
    fireEvent.click(screen.getByLabelText('#media-update · @muse · completed'));
    expect(sheet().getAttribute('data-sheet')).toBe('#media-update');
    expect(sheet().textContent).toContain('declared owner');
    expect(sheet().textContent).toContain('map the supplied media');
    expect(sheet().textContent).toContain('$0.02 · 8,310 tokens');
  });

  it('jumps to a loaded phase from its sheet', () => {
    const onPickSeq = vi.fn();
    strip(RUN, { onPickSeq });
    fireEvent.click(screen.getByLabelText('#media-update · @muse · completed'));
    fireEvent.click(screen.getByText('Jump to #media-update'));
    expect(onPickSeq).toHaveBeenCalledWith(40);
    expect(sheet()).toBeNull();
  });

  it('offers no jump for a phase that has not opened or is outside the loaded history, and says why', () => {
    strip(RUN, { onPickSeq: vi.fn(), loadedSeqs: new Set([43]) });
    fireEvent.click(screen.getByLabelText('#media-qa · @lens · pending'));
    expect(sheet().textContent).toContain('#media-qa has not opened yet');
    expect(screen.queryByText('Jump to #media-qa')).toBeNull();
    cleanup();
    strip(RUN, { onPickSeq: vi.fn(), loadedSeqs: new Set([43]) });
    fireEvent.click(screen.getByLabelText('#media-update · @muse · completed'));
    expect(sheet().textContent).toContain('outside the loaded history');
    expect(screen.queryByText('Jump to #media-update')).toBeNull();
  });

  it('keeps the separators out of the accessibility tree', () => {
    strip();
    const separators = screen.getAllByText('›');
    expect(separators).toHaveLength(3);
    for (const s of separators) {
      expect(s.getAttribute('data-a11y-hidden-ios')).toBe('true');
      expect(s.getAttribute('data-a11y-android')).toBe('no-hide-descendants');
    }
  });

  it('keeps run status out of the strip in every state', () => {
    const pill = (container) => container.querySelector('[data-pill]');
    expect(pill(strip().container)).toBeNull();
    expect(pill(strip({ ...RUN, status: 'between' }).container)).toBeNull();
    expect(pill(strip({ ...RUN, status: 'completed' }).container)).toBeNull();
  });

  it('hides the strip when an ad-hoc task nulls a run that was on screen', () => {
    const { container, rerender } = strip();
    expect(container.querySelector('[data-testid="strip"]')).toBeTruthy();
    rerender(<PipelineStrip run={null} phaseMap={PHASE_MAP} loadedSeqs={LOADED} />);
    expect(container.querySelector('[data-testid="strip"]')).toBeNull();
  });

  it('centres the current phase in the visible strip', () => {
    expect(centreOffset({ x: 600, width: 120 }, 360)).toBe(480);
    expect(centreOffset({ x: 40, width: 120 }, 360)).toBe(0);
  });

  it('fades the edge only on the side that actually hides phases', () => {
    const { container } = strip();
    const frame = (x, content, view) => ({
      nativeEvent: { contentOffset: { x }, contentSize: { width: content }, layoutMeasurement: { width: view } },
    });
    act(() => { h.onScroll(frame(0, 900, 400)); });
    expect(container.querySelectorAll('svg')).toHaveLength(1);
    act(() => { h.onScroll(frame(200, 900, 400)); });
    expect(container.querySelectorAll('svg')).toHaveLength(2);
    act(() => { h.onScroll(frame(0, 300, 400)); });
    expect(container.querySelectorAll('svg')).toHaveLength(0);
  });
});

describe('PipelineStrip between phases', () => {
  it('focuses the last finished phase when none is live, never the first', async () => {
    const { focusIndex } = await import('./PipelineStrip');
    const between = [{ state: 'completed' }, { state: 'skipped' }, { state: 'pending' }];
    expect(focusIndex(between)).toBe(1);
    expect(focusIndex([{ state: 'completed' }, { state: 'current' }])).toBe(1);
    expect(focusIndex([{ state: 'pending' }, { state: 'pending' }])).toBe(0);
  });

  it('never reopens a phase sheet for a run that replaced the one it was opened on', () => {
    const { rerender } = strip();
    fireEvent.click(screen.getByLabelText('#media-update · @muse · completed'));
    expect(sheet()).toBeTruthy();
    rerender(<PipelineStrip run={null} phaseMap={PHASE_MAP} profileOf={profileOf} loadedSeqs={LOADED} />);
    rerender(<PipelineStrip run={{ ...RUN, started_seq: 90 }} phaseMap={PHASE_MAP} profileOf={profileOf} loadedSeqs={LOADED} />);
    expect(sheet()).toBeNull();
  });
});
