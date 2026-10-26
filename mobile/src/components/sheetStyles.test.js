import { describe, expect, it } from 'vitest';

import { POPOVER_EDGE, POPOVER_GAP, popoverPosition } from './sheetStyles';

const anchor = { x: 700, y: 100, width: 44, height: 44 };

describe('popoverPosition', () => {
  it('sits under the anchor when there is room', () => {
    expect(popoverPosition(anchor, 852, 884, 530, 0).top).toBe(100 + 44 + POPOVER_GAP);
  });

  it('clamps so the list never runs past the bottom edge, safe area included', () => {
    const low = { x: 700, y: 800, width: 44, height: 44 };
    expect(popoverPosition(low, 852, 884, 530, 0).top).toBe(884 - 530 - POPOVER_EDGE);
    expect(popoverPosition(low, 852, 884, 530, 34).top).toBe(884 - 530 - POPOVER_EDGE - 34);
  });

  it('never rises above the top edge when the list is taller than the window', () => {
    expect(popoverPosition(anchor, 852, 400, 530, 0).top).toBe(POPOVER_EDGE);
  });
});
