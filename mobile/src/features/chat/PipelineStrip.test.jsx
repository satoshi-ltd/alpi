import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';

afterEach(cleanup);

const { fontOf } = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
}));

vi.mock('react-native', () => {
  const plain = ({ style, contentContainerStyle, onLayout, accessibilityLabel, ...rest }) => ({
    ...rest,
    ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
    'data-font': fontOf(style),
  });
  const View = ({ children, ...p }) => React.createElement('div', plain(p), children);
  const Text = ({ children, ...p }) => React.createElement('span', plain(p), children);
  const Pressable = ({ children, onPress, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...plain(p) }, children);
  const ScrollView = React.forwardRef(({ children, ...p }, ref) =>
    React.createElement('div', { ...plain(p), ref, 'data-testid': 'strip' }, children));
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

vi.mock('../../components/ActionSheet', () => ({
  ActionSheet: ({ open, title, subtitle, description, actions = [], onClose }) =>
    open
      ? React.createElement(
          'div',
          { 'data-sheet': subtitle ?? title },
          React.createElement('h3', null, title),
          description ? React.createElement('p', null, description) : null,
          ...actions.map((a) =>
            React.createElement(
              'button',
              {
                key: a.id,
                type: 'button',
                'data-detail': a.detail ?? '',
                onClick: () => {
                  onClose?.();
                  a.onPress?.();
                },
              },
              a.label,
            ),
          ),
        )
      : null,
}));

import { PipelineLauncher, PipelineStrip } from './PipelineStrip';

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

describe('PipelineStrip', () => {
  it('renders nothing without a run', () => {
    const { container } = render(<PipelineStrip run={null} accent="#f00" />);
    expect(container.textContent).toBe('');
  });

  it("labels the strip with the run's pipeline key, not the launch chain", () => {
    render(<PipelineStrip run={RUN} accent="#f00" />);
    expect(screen.getByText('media-update')).toBeTruthy();
    expect(screen.getByLabelText('#media-build current')).toBeTruthy();
  });

  it('renders every phase state, skipped distinct from completed', () => {
    render(<PipelineStrip run={RUN} accent="#f00" />);
    expect(screen.getByLabelText('#media-update completed')).toBeTruthy();
    expect(screen.getByLabelText('#media-config skipped')).toBeTruthy();
    expect(screen.getByLabelText('#media-qa pending')).toBeTruthy();
    const skipped = screen.getByLabelText('#media-config skipped');
    const completed = screen.getByLabelText('#media-update completed');
    expect(skipped.querySelector('[data-icon="x"]')).toBeTruthy();
    expect(completed.querySelector('[data-icon="check"]')).toBeTruthy();
  });

  it('renders a blocked run with the current phase blocked', () => {
    render(<PipelineStrip run={{ ...RUN, status: 'blocked' }} accent="#f00" />);
    expect(screen.getByLabelText('#media-build blocked')).toBeTruthy();
    expect(screen.getByLabelText('#media-build blocked').querySelector('[data-icon="ban"]')).toBeTruthy();
  });

  it('jumps to a phase seq and never offers a jump without one', () => {
    const onPickSeq = vi.fn();
    render(<PipelineStrip run={RUN} accent="#f00" onPickSeq={onPickSeq} />);
    fireEvent.click(screen.getByLabelText('#media-update completed'));
    expect(onPickSeq).toHaveBeenCalledWith(40);
    expect(screen.getByLabelText('#media-qa pending').tagName).toBe('DIV');
  });

  it('draws the phase separators as desktop PipelineStages does — an arrow in a theme font', () => {
    render(<PipelineStrip run={RUN} accent="#f00" />);
    const separators = screen.getAllByText('→');
    expect(separators).toHaveLength(3);
    for (const s of separators) expect(s.getAttribute('data-font')).toBe('Inter_400Regular');
  });

  it('hides the strip when an ad-hoc task nulls a run that was already on screen', () => {
    const { container, rerender } = render(<PipelineStrip run={RUN} accent="#f00" />);
    expect(container.querySelector('[data-testid="strip"]')).toBeTruthy();
    rerender(<PipelineStrip run={null} accent="#f00" />);
    expect(container.querySelector('[data-testid="strip"]')).toBeNull();
    expect(screen.queryByText('#media-update')).toBeNull();
  });
});

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
  phase_map: {
    setup: { owner: 'scout', task: 'collect the brief' },
    'media-update': { owner: 'pixel', task: 'refresh the photos' },
  },
};

const IDLE = { active: null, closed: [], blocked: null, pipeline_run: null };
const BUSY = { active: { slug: 'build', title: 'wire it', opened_seq: 12 }, closed: [], blocked: null, pipeline_run: null };
const UNFINISHED = {
  active: null,
  closed: [],
  blocked: null,
  pipeline_run: {
    pipeline: 'media-update',
    status: 'between',
    started_seq: 37,
    current_phase: 'media-config',
    phases: [
      { slug: 'media-update', state: 'completed', seq: 40 },
      { slug: 'media-config', state: 'completed', seq: 42 },
      { slug: 'media-build', state: 'pending', seq: null },
      { slug: 'media-qa', state: 'pending', seq: null },
    ],
  },
};

function launchButton() {
  return screen.getByLabelText('run a pipeline');
}

function openPicker() {
  fireEvent.click(launchButton());
}

function sheet(container, subtitle) {
  return container.querySelector(`[data-sheet="${subtitle}"]`);
}

describe('PipelineLauncher', () => {
  it('is hidden for a subscriber', () => {
    const { container } = render(
      <PipelineLauncher workgroup={{ ...WG, is_hub: false }} tasks={IDLE} accent="#f00" onRun={() => {}} />,
    );
    expect(container.textContent).toBe('');
  });

  it('is hidden when no declared chain can be triggered', () => {
    const wg = { ...WG, phase_map: { setup: { owner: 'scout' }, 'media-update': {} } };
    const { container } = render(<PipelineLauncher workgroup={wg} tasks={IDLE} accent="#f00" onRun={() => {}} />);
    expect(container.textContent).toBe('');
  });

  it('is hidden for a deliberation workgroup', () => {
    const { container } = render(
      <PipelineLauncher workgroup={{ id: 'w2', is_hub: true, pipelines: {} }} tasks={IDLE} accent="#f00" onRun={() => {}} />,
    );
    expect(container.textContent).toBe('');
  });

  it('lists only the triggerable chains declared by the recipe', () => {
    const wg = {
      ...WG,
      phase_map: { setup: { owner: 'scout', task: 'collect the brief' }, 'media-update': { owner: 'pixel' } },
    };
    const { container } = render(<PipelineLauncher workgroup={wg} tasks={IDLE} accent="#f00" onRun={() => {}} />);
    expect(screen.getByText('1 chain declared by the recipe')).toBeTruthy();
    openPicker();
    const picker = sheet(container, 'DECLARED BY THE RECIPE');
    expect(within(picker).getByText('#setup')).toBeTruthy();
    expect(within(picker).queryByText('#media-update')).toBeNull();
  });

  it('shows every triggerable chain with its phase count', () => {
    const { container } = render(<PipelineLauncher workgroup={WG} tasks={IDLE} accent="#f00" onRun={() => {}} />);
    expect(screen.getByText('2 chains declared by the recipe')).toBeTruthy();
    openPicker();
    const picker = sheet(container, 'DECLARED BY THE RECIPE');
    expect(within(picker).getByText('#setup').getAttribute('data-detail')).toBe('4 phases');
    expect(within(picker).getByText('#media-update').getAttribute('data-detail')).toBe('4 phases');
  });

  it('is unavailable while a task is open and says which', () => {
    render(<PipelineLauncher workgroup={WG} tasks={BUSY} accent="#f00" onRun={() => {}} />);
    expect(launchButton().disabled).toBe(true);
    expect(screen.getByText(/#build is still open/)).toBeTruthy();
    openPicker();
    expect(screen.queryByText('#setup')).toBeNull();
  });

  it('is unavailable while the workgroup is paused and says so', () => {
    render(<PipelineLauncher workgroup={{ ...WG, paused: true }} tasks={IDLE} accent="#f00" onRun={() => {}} />);
    expect(launchButton().disabled).toBe(true);
    expect(screen.getByText(/resume the workgroup/)).toBeTruthy();
  });

  it('confirms with the pipeline key and its declared first task, then runs it', () => {
    const onRun = vi.fn();
    const { container } = render(<PipelineLauncher workgroup={WG} tasks={IDLE} accent="#f00" onRun={onRun} />);
    openPicker();
    fireEvent.click(within(sheet(container, 'DECLARED BY THE RECIPE')).getByText('#media-update'));
    const confirm = sheet(container, 'PIPELINE TRIGGER');
    expect(confirm.textContent).toContain('Run #media-update');
    expect(confirm.textContent).toContain('@pixel opens #media-update');
    expect(confirm.textContent).toContain('refresh the photos');
    fireEvent.click(within(confirm).getByRole('button', { name: 'Run #media-update' }));
    expect(onRun).toHaveBeenCalledTimes(1);
    expect(onRun.mock.calls[0][0].key).toBe('media-update');
  });

  it('an unfinished run restarts the chain instead of resuming it', () => {
    const { container } = render(<PipelineLauncher workgroup={WG} tasks={UNFINISHED} accent="#f00" onRun={() => {}} />);
    openPicker();
    const picker = sheet(container, 'DECLARED BY THE RECIPE');
    expect(within(picker).getByText('#media-update').getAttribute('data-detail')).toBe('between · #media-config');
    fireEvent.click(within(picker).getByText('#media-update'));
    const confirm = sheet(container, 'PIPELINE TRIGGER');
    expect(within(confirm).getByRole('button', { name: 'Run #media-update' })).toBeTruthy();
    expect(confirm.textContent).toContain('restarts it from #media-update');
    expect(confirm.textContent).toContain('does not resume');
    expect(confirm.textContent).not.toContain('Resume');
  });

  it('offers Run again only once that chain completed', () => {
    const done = { ...UNFINISHED, pipeline_run: { ...UNFINISHED.pipeline_run, status: 'completed' } };
    const { container } = render(<PipelineLauncher workgroup={WG} tasks={done} accent="#f00" onRun={() => {}} />);
    openPicker();
    const picker = sheet(container, 'DECLARED BY THE RECIPE');
    expect(within(picker).getByText('#media-update').getAttribute('data-detail')).toBe('completed');
    fireEvent.click(within(picker).getByText('#media-update'));
    const confirm = sheet(container, 'PIPELINE TRIGGER');
    expect(within(confirm).getByRole('button', { name: 'Run again #media-update' })).toBeTruthy();
    expect(confirm.textContent).not.toContain('restarts');
  });
});
