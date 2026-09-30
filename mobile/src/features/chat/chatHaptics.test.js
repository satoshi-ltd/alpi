import { describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ calls: [] }));

vi.mock('../../lib/haptics', () => ({
  tap: () => { h.calls.push('tap'); },
  selection: () => { h.calls.push('selection'); },
}));

import { longPressHaptic, sendHaptic } from './chatHaptics';

describe('chat haptics', () => {
  it('send is a light impact, long press a selection tick', () => {
    sendHaptic();
    longPressHaptic();
    expect(h.calls).toEqual(['tap', 'selection']);
  });
});
