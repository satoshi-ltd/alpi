import { describe, it, expect } from 'vitest';

import { fmtDuration, thoughtLabel } from './reasoningLabel';

describe('thoughtLabel', () => {
  it('omits the duration when reasoned_s is missing or sub-second', () => {
    expect(thoughtLabel(null)).toBe('Thought');
    expect(thoughtLabel(undefined)).toBe('Thought');
    expect(thoughtLabel(0)).toBe('Thought');
    expect(thoughtLabel(0.4)).toBe('Thought');
  });
  it('shows the duration for a real value', () => {
    expect(thoughtLabel(11)).toBe('Thought for 11s');
    expect(thoughtLabel(90)).toBe('Thought for 1m 30s');
  });
});

describe('fmtDuration', () => {
  it('formats seconds and minutes', () => {
    expect(fmtDuration(5)).toBe('5s');
    expect(fmtDuration(60)).toBe('1m');
    expect(fmtDuration(75)).toBe('1m 15s');
  });
});
