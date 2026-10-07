import { describe, expect, it, vi } from 'vitest';

import { onInboxSignal, signalInbox } from './inboxSignal';

describe('inboxSignal', () => {
  it('tells every listener which connection changed until it unsubscribes', () => {
    const a = vi.fn();
    const b = vi.fn(() => { throw new Error('boom'); });
    const offA = onInboxSignal(a);
    const offB = onInboxSignal(b);

    signalInbox('c2');
    expect(a).toHaveBeenCalledWith('c2');
    expect(b).toHaveBeenCalledWith('c2');

    offA();
    offB();
    signalInbox('c3');
    expect(a).toHaveBeenCalledTimes(1);
  });
});
