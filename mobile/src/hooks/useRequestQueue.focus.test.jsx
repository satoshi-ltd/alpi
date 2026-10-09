import React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ call: vi.fn(), endpoint: { id: 'c1' }, listeners: new Set(), dismiss: vi.fn() }));

vi.mock('../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call, endpoint: h.endpoint }) }));
vi.mock('../features/aln/dismiss', () => ({ dismissRequestNotifications: h.dismiss }));
vi.mock('./useEvents', () => ({
  useEventEffect: (kinds, fn) => {
    React.useEffect(() => {
      const listener = (ev) => { if (kinds.includes(ev.event)) fn(ev); };
      h.listeners.add(listener);
      return () => h.listeners.delete(listener);
    });
  },
}));

import { focusRequest, promote, useRequestQueue } from './useRequestQueue';

const enqueue = (q, req) => (q.some((r) => r.request_id === req.request_id) ? q : [...q, { request_id: req.request_id }]);

let seen = null;
function Probe({ domain = 'approval' }) {
  seen = useRequestQueue(domain, enqueue);
  return null;
}

const ids = () => seen.queue.map((r) => r.request_id);
const pending = (...list) => ({ requests: list.map((request_id) => ({ request_id })) });

beforeEach(() => {
  h.call.mockReset();
  h.dismiss.mockClear();
  h.listeners.clear();
  h.endpoint = { id: 'c1' };
  seen = null;
});
afterEach(cleanup);

describe('promote', () => {
  it('moves one request to the front and keeps the rest in order', () => {
    const q = [{ request_id: 'a' }, { request_id: 'b' }, { request_id: 'c' }];
    expect(promote(q, 'c').map((r) => r.request_id)).toEqual(['c', 'a', 'b']);
    expect(promote(q, 'a')).toBe(q);
    expect(promote(q, 'zz')).toBe(q);
  });
});

describe('focusRequest', () => {
  it('brings a queued request to the front of its own sheet only', async () => {
    h.call.mockResolvedValue(pending('a', 'b'));
    render(<Probe />);
    await act(async () => {});
    await act(async () => { focusRequest('clarification', 'b'); });
    expect(ids()).toEqual(['a', 'b']);
    await act(async () => { focusRequest('approval', 'b'); });
    expect(ids()).toEqual(['b', 'a']);
  });

  it('refetches pending once when the focused request has not arrived yet', async () => {
    h.call.mockResolvedValueOnce(pending('a'));
    render(<Probe />);
    await act(async () => {});
    h.call.mockResolvedValueOnce(pending('a', 'late'));
    await act(async () => { focusRequest('approval', 'late'); });
    await act(async () => {});
    expect(ids()).toEqual(['late', 'a']);
  });

  it('gives up after one refetch when the request is already gone', async () => {
    h.call.mockResolvedValue(pending('a'));
    render(<Probe />);
    await act(async () => {});
    h.call.mockClear();
    await act(async () => { focusRequest('approval', 'gone'); });
    await act(async () => {});
    expect(h.call).toHaveBeenCalledTimes(1);
    expect(ids()).toEqual(['a']);
  });

  it('keeps waiting across a connection switch until the new connection lists the request', async () => {
    h.call.mockResolvedValue(pending('old'));
    const { rerender } = render(<Probe />);
    await act(async () => {});
    let release;
    h.call.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
    await act(async () => { focusRequest('approval', 'r9', 'c2'); });
    await act(async () => { release?.(pending('old')); });
    h.endpoint = { id: 'c2' };
    h.call.mockResolvedValue(pending('x', 'r9'));
    rerender(<Probe />);
    await act(async () => {});
    await act(async () => {});
    expect(ids()).toEqual(['r9', 'x']);
  });
});

describe('resolved requests', () => {
  it('drops the request and its delivered notification', async () => {
    h.call.mockResolvedValue(pending('a', 'b'));
    render(<Probe />);
    await act(async () => {});
    await act(async () => { for (const fn of [...h.listeners]) fn({ event: 'approval.resolved', data: { request_id: 'a' } }); });
    expect(ids()).toEqual(['b']);
    expect(h.dismiss).toHaveBeenCalledWith('a');
  });
});

describe('a pending prompt survives a refreshed connection object', () => {
  it('keeps the queue, and asks nothing again, when the same endpoint arrives as a new object', async () => {
    h.call.mockResolvedValue(pending('a'));
    const view = render(<Probe />);
    await act(async () => {});
    expect(ids()).toEqual(['a']);
    h.call.mockClear();
    h.endpoint = { id: 'c1', label: 'renamed' };
    h.call = vi.fn(async () => pending());
    view.rerender(<Probe />);
    await act(async () => {});
    expect(ids()).toEqual(['a']);
    expect(h.call).not.toHaveBeenCalled();
  });

  it('still drops the queue and asks the new daemon when the endpoint really changes', async () => {
    h.call.mockResolvedValue(pending('a'));
    const view = render(<Probe />);
    await act(async () => {});
    h.call.mockResolvedValue(pending('b'));
    h.endpoint = { id: 'c2' };
    view.rerender(<Probe />);
    await act(async () => {});
    expect(ids()).toEqual(['b']);
  });
});
