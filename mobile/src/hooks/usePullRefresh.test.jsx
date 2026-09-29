import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';

import { usePullRefresh } from './usePullRefresh';

afterEach(cleanup);

function Probe({ refresh }) {
  const { refreshing, onRefresh } = usePullRefresh(refresh);
  return React.createElement('button', { type: 'button', onClick: onRefresh, 'data-refreshing': String(refreshing) }, 'pull');
}

describe('usePullRefresh', () => {
  it('shows the spinner while the refresh runs and hides it after, even when it fails', async () => {
    let release;
    const refresh = vi.fn(() => new Promise((resolve) => { release = resolve; }));
    render(<Probe refresh={refresh} />);
    const btn = screen.getByText('pull');
    await act(async () => { btn.click(); });
    expect(btn.getAttribute('data-refreshing')).toBe('true');
    await act(async () => { release(); });
    expect(btn.getAttribute('data-refreshing')).toBe('false');

    const failing = vi.fn(async () => { throw new Error('offline'); });
    cleanup();
    render(<Probe refresh={failing} />);
    await act(async () => { screen.getByText('pull').click(); });
    expect(screen.getByText('pull').getAttribute('data-refreshing')).toBe('false');
  });
});
