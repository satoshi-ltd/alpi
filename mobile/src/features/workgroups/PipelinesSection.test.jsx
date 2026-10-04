import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const plain = ({ style, ...rest }) => rest;
  const View = ({ children, ...p }) => React.createElement('div', plain(p), children);
  const Text = ({ children, ...p }) => React.createElement('span', plain(p), children);
  const Pressable = ({ children, onPress, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...plain(p) }, children);
  return { View, Text, Pressable, StyleSheet: { create: (s) => s } };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line2: '#eee', bgInput: '#fafafa', hover: '#f4f4f4', danger: '#c00' },
    fonts: { mono: 'm', monoSemibold: 'ms', monoMedium: 'mm', sans: { regular: 's' } },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));

vi.mock('../../components/Fold', () => ({
  Fold: ({ fold, unfolded, pulse }) =>
    React.createElement('i', { 'data-fold': fold, 'data-unfolded': unfolded ? '1' : undefined, 'data-pulse': pulse ? '1' : undefined }),
}));

vi.mock('../../components/Icon', () => ({
  Icon: ({ name }) => React.createElement('i', { 'data-icon': name }),
}));

vi.mock('../../components/Row', () => ({
  SectionHeader: ({ children }) => React.createElement('h2', null, children),
  RowGroup: ({ children }) => React.createElement('section', null, children),
  RowSeparator: () => React.createElement('hr', null),
  Row: ({ label, helper, onPress, disabled }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: disabled ? undefined : onPress,
        disabled: !!disabled || !onPress,
        'data-helper': helper ?? '',
      },
      label,
    ),
}));

import { PipelinesSection } from './PipelinesSection';

const PROFILES = { scout: { fold: 'house', accent: '#f05940' }, pixel: { fold: 'rocket', accent: '#2cb3b5' } };
const profileOf = (name) => PROFILES[name] ?? null;

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

describe('PipelinesSection', () => {
  it('lists every declared chain, launch first, phases in order', () => {
    render(<PipelinesSection workgroup={WG} />);
    expect(screen.getAllByText(/^#/).map((n) => n.textContent)).toEqual([
      '#setup', '#enrich', '#build', '#qa',
      '#media-update', '#media-config', '#media-build', '#media-qa',
    ]);
    expect(screen.getByText('setup')).toBeTruthy();
    expect(screen.getByText('starts at launch')).toBeTruthy();
    expect(screen.getByText('on demand')).toBeTruthy();
  });

  it('marks each phase with its declared owner and the run state, on the run chain only', () => {
    const run = {
      pipeline: 'setup',
      status: 'running',
      cost: { usd: 1.5 },
      phases: [
        { slug: 'setup', state: 'completed' },
        { slug: 'enrich', state: 'current' },
        { slug: 'build', state: 'pending' },
        { slug: 'qa', state: 'pending' },
      ],
    };
    const { container } = render(<PipelinesSection workgroup={WG} run={run} profileOf={profileOf} />);
    expect(screen.getByText('last run running · 1 of 4 · $1.50')).toBeTruthy();
    const setupChip = container.querySelector('[testID="phase-setup"]');
    expect(setupChip.querySelector('[data-fold="house"]')).toBeTruthy();
    expect(setupChip.querySelector('[data-icon="check"]')).toBeTruthy();
    expect(container.querySelector('[testID="phase-enrich"]').textContent).toContain('running');
    expect(container.querySelector('[testID="phase-enrich"]').querySelector('[data-fold]')).toBeNull();
    expect(container.querySelector('[testID="phase-media-update"]').querySelector('[data-fold="rocket"]')).toBeTruthy();
    expect(screen.getAllByText(/^last run/)).toHaveLength(1);
  });

  it('draws an owner with no local profile as the grey unfolded object, and a blocked phase in words', () => {
    const run = { pipeline: 'setup', status: 'blocked', phases: [{ slug: 'setup', state: 'current' }] };
    const { container } = render(<PipelinesSection workgroup={WG} run={run} profileOf={() => null} />);
    const chip = container.querySelector('[testID="phase-setup"]');
    expect(chip.querySelector('[data-unfolded="1"]')).toBeTruthy();
    expect(chip.textContent).toContain('blocked');
  });

  it('lists chains in recipe order after the launch chain, like desktop', () => {
    render(<PipelinesSection workgroup={{ ...WG, launch_pipeline: null, pipelines: { 'z-last': ['z-last'], 'a-first': ['a-first'] }, phase_map: {} }} />);
    expect(screen.getAllByText(/^#/).map((n) => n.textContent)).toEqual(['#z-last', '#a-first']);
  });

  it('says the chains come from the recipe and are read-only', () => {
    render(<PipelinesSection workgroup={WG} />);
    expect(screen.getByText('Read-only — a recipe declares these chains.')).toBeTruthy();
  });

  it('instructs no control this build has — nothing points at running a chain from the chat', () => {
    const withLaunch = render(<PipelinesSection workgroup={WG} />);
    expect(withLaunch.container.textContent).not.toMatch(/from the chat/i);
    withLaunch.unmount();
    const launchless = render(<PipelinesSection workgroup={{ ...WG, launch_pipeline: null }} />);
    expect(launchless.container.textContent).not.toMatch(/from the chat/i);
  });

  it('offers no action at all — no Run, no editor', () => {
    render(<PipelinesSection workgroup={WG} />);
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.queryByText(/^Run #/)).toBeNull();
    expect(screen.queryByText('Launch pipeline')).toBeNull();
  });

  it('a subscriber sees the same read-only section', () => {
    render(<PipelinesSection workgroup={{ ...WG, is_hub: false }} />);
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.getAllByText('#setup').length).toBeGreaterThan(0);
    expect(screen.getByText(/Read-only/)).toBeTruthy();
  });

  it('explains the launchless case instead of looking empty', () => {
    render(<PipelinesSection workgroup={{ ...WG, launch_pipeline: null }} />);
    expect(screen.queryByText('starts at launch')).toBeNull();
    expect(screen.getByText(/Nothing starts until a trigger\./)).toBeTruthy();
    expect(screen.getAllByText('on demand')).toHaveLength(2);
  });

  it('a workgroup with no chain reads as deliberation', () => {
    render(
      <PipelinesSection workgroup={{ id: 'w2', profile: 'doc', is_hub: true, pipelines: {}, launch_pipeline: null }} />,
    );
    expect(screen.getByText(/deliberation workgroup/)).toBeTruthy();
    expect(screen.queryByText(/Read-only/)).toBeNull();
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });

  it('ignores a retired pipeline list', () => {
    render(<PipelinesSection workgroup={{ id: 'w3', is_hub: true, pipeline: ['legacy'], pipelines: {} }} />);
    expect(screen.queryByText('#legacy')).toBeNull();
    expect(screen.getByText(/deliberation workgroup/)).toBeTruthy();
  });

  it('names the retired shape the daemon refuses to load instead of reading as deliberation', () => {
    render(
      <PipelinesSection
        workgroup={{ id: 'w4', is_hub: true, pipeline: ['legacy'], pipelines: {}, needs_relaunch: true }}
      />,
    );
    expect(screen.getByText(/Retired pipeline shape\. The daemon skips this workgroup/)).toBeTruthy();
    expect(screen.getByText(/relaunch it from its recipe/)).toBeTruthy();
    expect(screen.queryByText(/deliberation workgroup/)).toBeNull();
    expect(screen.queryByText('#legacy')).toBeNull();
  });
});
