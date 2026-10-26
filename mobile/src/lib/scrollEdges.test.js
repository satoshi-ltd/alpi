import { describe, expect, it } from 'vitest';

import { scrollEdges } from './scrollEdges';

const frame = (x, content, view) => ({ contentOffset: { x }, contentSize: { width: content }, layoutMeasurement: { width: view } });

describe('scrollEdges', () => {
  it('shows only the right edge at the start of a strip that overflows', () => {
    expect(scrollEdges(frame(0, 800, 390))).toEqual({ left: false, right: true });
  });

  it('shows both edges in the middle', () => {
    expect(scrollEdges(frame(200, 800, 390))).toEqual({ left: true, right: true });
  });

  it('shows only the left edge at the end', () => {
    expect(scrollEdges(frame(410, 800, 390))).toEqual({ left: true, right: false });
  });

  it('shows nothing when the content fits', () => {
    expect(scrollEdges(frame(0, 360, 390))).toEqual({ left: false, right: false });
  });
});
