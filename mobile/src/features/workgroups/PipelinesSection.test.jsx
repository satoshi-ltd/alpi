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
    colors: { ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line2: '#eee', bgInput: '#fafafa' },
    fonts: { mono: 'm', monoSemibold: 'ms', monoMedium: 'mm', sans: { regular: 's' } },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));

vi.mock('../../components/Pill', () => ({
  Pill: ({ children, tone, off }) =>
    React.createElement('span', { 'data-pill': tone ?? (off ? 'off' : 'plain') }, children),
}));

vi.mock('../../components/Row', () => ({
  SectionHeader: ({ children }) => React.createElement('h2', null, children),
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
      '#setup', '#setup', '#enrich', '#build', '#qa',
      '#media-update', '#media-update', '#media-config', '#media-build', '#media-qa',
    ]);
    expect(screen.getByText('launch')).toBeTruthy();
    expect(screen.getByText('on demand')).toBeTruthy();
  });

  it('says the chains come from the recipe and are read-only', () => {
    render(<PipelinesSection workgroup={WG} />);
    expect(screen.getByText(/Read-only — a recipe declares these chains/)).toBeTruthy();
    expect(screen.getByText(/Run one from the chat/)).toBeTruthy();
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
    expect(screen.queryByText('launch')).toBeNull();
    expect(screen.getByText(/hub stays idle until a chain is started from the chat/)).toBeTruthy();
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
});
