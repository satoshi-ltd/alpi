import { describe, expect, it } from 'vitest';

import { BUSY_DIM, busyFacetDelays } from '../../../common/busy.mjs';
import { busyLevel, busyWaveRange } from './busyWave';

const at = ({ inputRange, outputRange }, t) => {
  const i = inputRange.findIndex((x, k) => t >= x && t <= inputRange[k + 1]);
  const [x0, x1] = [inputRange[i], inputRange[i + 1]];
  return outputRange[i] + ((outputRange[i + 1] - outputRange[i]) * (t - x0)) / (x1 - x0);
};

describe('busy wave', () => {
  it('runs each facet from full ink down to the dim level and back', () => {
    expect(busyLevel(0)).toBe(1);
    expect(busyLevel(0.5)).toBeCloseTo(BUSY_DIM);
    expect(busyLevel(1)).toBe(1);
  });

  it('starts an undelayed facet at full ink and dims it halfway through the loop', () => {
    const range = busyWaveRange(0);
    expect(range.inputRange).toEqual([0, 0.5, 1]);
    expect(range.outputRange).toEqual([1, BUSY_DIM, 1]);
  });

  it('offsets every facet by its shared delay so the loop is seamless and strictly ordered', () => {
    for (const delay of busyFacetDelays()) {
      const range = busyWaveRange(delay);
      expect(range.inputRange[0]).toBe(0);
      expect(range.inputRange.at(-1)).toBe(1);
      expect([...range.inputRange].sort((a, b) => a - b)).toEqual(range.inputRange);
      expect(new Set(range.inputRange).size).toBe(range.inputRange.length);
      expect(range.outputRange[0]).toBeCloseTo(range.outputRange.at(-1), 3);
      expect(Math.min(...range.outputRange)).toBeCloseTo(BUSY_DIM, 3);
    }
  });

  it('matches the desktop CSS wave: a negative delay starts the facet that far into its loop', () => {
    const delay = busyFacetDelays()[0];
    const range = busyWaveRange(delay);
    const into = (-delay / 1.6) % 1;
    expect(at(range, 0)).toBeCloseTo(busyLevel(into), 3);
    expect(at(range, 0.25)).toBeCloseTo(busyLevel((into + 0.25) % 1), 3);
  });
});
