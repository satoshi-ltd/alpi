import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  call: vi.fn(async () => ({ cancelled: true })),
  refresh: vi.fn(async () => null),
}));

vi.mock('react-native', () => {
  const View = ({ children, ...props }) => React.createElement('div', props, children);
  return { ScrollView: View };
});
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, subtitle, children }) => open ? <section><h1>{title}</h1><p>{subtitle}</p>{children}</section> : null,
}));
vi.mock('../../components/Row', () => ({
  Row: ({ label, helper, value, onPress }) => <button type="button" onClick={onPress}><span>{label}</span><small>{helper}</small><i>{value}</i></button>,
  RowSeparator: () => <hr />,
}));
vi.mock('../../hooks/useDaemonData', () => ({
  useRunsList: () => ({
    loading: false,
    data: { runs: [{ id: 'r1', status: 'running', source: 'user', model: 'm', event_count: 3 }] },
    refresh: h.refresh,
  }),
}));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call }) }));

import { RunsSheet } from './RunsSheet';

beforeEach(() => {
  h.call.mockReset().mockResolvedValue({ cancelled: true });
  h.refresh.mockReset().mockResolvedValue(null);
});
afterEach(cleanup);

it('shows and cancels a durable run', async () => {
  render(<RunsSheet open profile="doc" onClose={() => {}} />);
  expect(screen.getByText('@doc · 1 run')).toBeTruthy();
  fireEvent.click(screen.getByText(/r1/));
  await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.run.cancel', { profile: 'doc', id: 'r1' }));
  expect(h.refresh).toHaveBeenCalled();
});

it('contains cancellation failures', async () => {
  h.call.mockRejectedValueOnce(new Error('offline'));
  render(<RunsSheet open profile="doc" onClose={() => {}} />);

  fireEvent.click(screen.getByText(/r1/));

  await waitFor(() => expect(screen.getByText('Could not stop run')).toBeTruthy());
  expect(h.refresh).not.toHaveBeenCalled();
});
