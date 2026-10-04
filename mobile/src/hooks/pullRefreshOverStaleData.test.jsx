import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';

const h = vi.hoisted(() => ({ toast: vi.fn(), call: vi.fn() }));
vi.mock("../theme/ThemeContext", () => ({ useTheme: () => ({ colors: { accent: "#14110c" } }) }));
vi.mock('../components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../lib/haptics', () => ({ selection: vi.fn() }));

import { EndpointContext } from '../lib/EndpointContext';
import { _resetDaemonDataCache, useProfileSummaries } from './useDaemonData';
import { usePullRefresh } from './usePullRefresh';

afterEach(() => {
  cleanup();
  _resetDaemonDataCache();
  h.toast.mockClear();
  h.call.mockReset();
});

function Screen() {
  const summaries = useProfileSummaries();
  const { onRefresh } = usePullRefresh(summaries.refresh);
  return (
    <button type="button" onClick={onRefresh}>
      {summaries.data?.profiles?.[0]?.name ?? 'empty'}
    </button>
  );
}

function mount() {
  return render(
    <EndpointContext.Provider value={{ endpoint: { id: 'screen-1' }, call: h.call }}>
      <Screen />
    </EndpointContext.Provider>,
  );
}

describe('pull to refresh on a screen that already shows data', () => {
  it('tells the reader when the refresh failed and keeps the stale list', async () => {
    h.call.mockResolvedValueOnce({ profiles: [{ name: 'doc' }] }).mockRejectedValueOnce(new Error('offline'));
    mount();
    await waitFor(() => expect(screen.getByRole('button').textContent).toBe('doc'));

    await act(async () => { screen.getByRole('button').click(); });

    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Refresh failed', message: 'offline' }));
    expect(screen.getByRole('button').textContent).toBe('doc');
  });

  it('stays quiet when the refresh works', async () => {
    h.call.mockResolvedValue({ profiles: [{ name: 'doc' }] });
    mount();
    await waitFor(() => expect(screen.getByRole('button').textContent).toBe('doc'));

    await act(async () => { screen.getByRole('button').click(); });

    expect(h.toast).not.toHaveBeenCalled();
  });
});
