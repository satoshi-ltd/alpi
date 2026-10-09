import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const h = vi.hoisted(() => ({ height: 800, fontScale: 1 }));

vi.mock('react-native', () => {
  const View = ({ children, accessibilityRole }) => React.createElement('div', { role: accessibilityRole }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel, disabled }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, disabled }, typeof children === 'function' ? children({ pressed: false }) : children);
  return { View, Text, Pressable, useWindowDimensions: () => ({ height: h.height, fontScale: h.fontScale }) };
});
vi.mock('../../components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('h2', {}, children) }));
vi.mock('../../components/Fold', () => ({ Fold: () => null }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../hooks/useDaemonData', () => ({ useProfileSummaries: () => ({ data: { profiles: [] } }) }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { hover: '#eee', line: '#ddd', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', bgPane: '#fff', warning: '#e08a3c', warningText: '#8a5a0a', accent: '#a70', danger: '#c14545', dangerText: '#b73737', selected: '#eee' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'mono' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { BAND_MAX, NeedsYouBand, bandMax, bandOf } from './NeedsYouBand';

afterEach(() => {
  cleanup();
  h.height = 800;
  h.fontScale = 1;
});

const NOW = Date.now() / 1000;
const approval = (n) => ({ kind: 'approval', request_id: `r${n}`, profile: 'abby', title: `command ${n}`, ts: NOW - 60 * n });
const failedJob = { profile: 'clonara', job_id: 'j1', title: 'weekly labs', last_run_status: 'error', last_run_at: NOW - 3 * 3600, next_fire: null };
const empty = { needsYou: [], running: [], scheduled: [] };

function mount(activity, props = {}) {
  return render(<NeedsYouBand activity={activity} nowSec={NOW} onOpen={vi.fn()} onRun={vi.fn()} {...props} />);
}

describe('needs-you band', () => {
  it('is absent while nothing waits', () => {
    const { container } = mount(empty);
    expect(container.firstChild).toBeNull();
    expect(bandOf(empty, NOW)).toBeNull();
    cleanup();
    expect(mount({ ...empty, running: [{ kind: 'turn', profile: 'doc', session_id: 's' }], scheduled: [{ profile: 'doc', job_id: 'ok', title: 'fine', next_fire: new Date((NOW + 60) * 1000).toISOString(), last_run_status: 'ok' }] }).container.firstChild).toBeNull();
  });

  it('lists an approval and a failed job with the same actions as Activity', () => {
    const onOpen = vi.fn();
    const onRun = vi.fn();
    mount({ ...empty, needsYou: [approval(1)], scheduled: [failedJob] }, { onOpen, onRun });
    expect(screen.getByText('Needs you · 2')).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/^abby · command 1, approval/));
    expect(onOpen).toHaveBeenCalledWith({ type: 'request', domain: 'approval', requestId: 'r1' });
    fireEvent.click(screen.getByLabelText('Run again clonara · weekly labs'));
    expect(onRun).toHaveBeenCalledWith({ profile: 'clonara', jobId: 'j1' });
    fireEvent.click(screen.getByLabelText(/^clonara · weekly labs, failed 3h ago$/));
    expect(onOpen).toHaveBeenLastCalledWith({ type: 'path', path: '/profile/clonara/schedule/j1' });
  });

  it('shows three rows at most but counts them all, and its title opens Activity', () => {
    const onOpenActivity = vi.fn();
    mount({ ...empty, needsYou: [1, 2, 3, 4].map(approval), scheduled: [failedJob] }, { onOpenActivity });
    expect(BAND_MAX).toBe(3);
    expect(screen.getByText('Needs you · 5')).toBeTruthy();
    expect(screen.getAllByRole('button', { name: /command|weekly/ }).length).toBe(3);
    fireEvent.click(screen.getByLabelText('Activity, 5 waiting'));
    expect(onOpenActivity).toHaveBeenCalled();
  });

  it('has no job to show a member, who gets approvals and questions only', () => {
    mount({ ...empty, needsYou: [approval(1), { kind: 'clarification', request_id: 'q1', profile: 'doc', title: 'Which?', ts: NOW - 5 }] });
    expect(screen.getByText('Needs you · 2')).toBeTruthy();
    expect(screen.queryByLabelText(/Run again/)).toBeNull();
  });

  it('leaves out the Activity link when Activity is unavailable', () => {
    mount({ ...empty, needsYou: [approval(1)] }, { onOpenActivity: null });
    expect(screen.queryByLabelText(/^Activity,/)).toBeNull();
  });

  it('shows one row, still counting them all, on a short screen or at large text so the roster keeps its room', () => {
    expect(bandMax({ height: 800, fontScale: 1 })).toBe(BAND_MAX);
    expect(bandMax({ height: 400, fontScale: 1 })).toBe(1);
    expect(bandMax({ height: 800, fontScale: 1.3 })).toBe(1);
    h.fontScale = 1.3;
    mount({ ...empty, needsYou: [approval(1), approval(2), approval(3), approval(4)] });
    expect(screen.getByText('Needs you · 4')).toBeTruthy();
    expect(screen.queryAllByText(/command \d/)).toHaveLength(1);
  });
});
