import { BUSY_DIM, BUSY_WAVE_S } from '../../../common/busy.mjs';

const round = (v) => Math.round(v * 1e4) / 1e4;

export function busyLevel(u) {
  return u <= 0.5 ? 1 - (1 - BUSY_DIM) * 2 * u : BUSY_DIM + (1 - BUSY_DIM) * (2 * u - 1);
}

export function busyWaveRange(delay) {
  const phase = (((-delay / BUSY_WAVE_S) % 1) + 1) % 1;
  const inputRange = [...new Set([0, 1, (1 - phase) % 1, (1.5 - phase) % 1].map(round))].sort((a, b) => a - b);
  const outputRange = inputRange.map((t) => round(busyLevel(round((t + phase) % 1))));
  return { inputRange, outputRange };
}
