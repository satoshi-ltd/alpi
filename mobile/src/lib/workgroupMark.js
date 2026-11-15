import { WG_ALPHA, WG_CELLS, WG_FRONTAL, WG_GAP, WG_GAP_PX, WG_ORDER, WG_RING, WG_STATES, WG_STILLS, WG_TURNS } from '../../../common/workgroupMark.mjs';
import { MARK_SIZES, SMALL, TURN } from '../../../common/agentMarks.mjs';

const GAPS = Object.keys(WG_CELLS).map((key) => [Number(key), key]);

export const FILL_TRACK = { dur: 2.4, times: [0, 0.5, 1], values: [[WG_ALPHA.chase], [1], [WG_ALPHA.chase]] };
export const CHASE_TRACK = { dur: 2.4, times: [0, 0.12, 0.3, 0.46, 1], values: [[WG_ALPHA.chase], [1], [1], [WG_ALPHA.chase], [WG_ALPHA.chase]] };
export const CHASE_LAG = 0.8;

export function cellPaths(px) {
  const want = Math.round(Math.max(WG_GAP, (WG_GAP_PX * 100) / px) * 10) / 10;
  const [, key] = GAPS.reduce((best, g) => (Math.abs(g[0] - want) < Math.abs(best[0] - want) ? g : best), GAPS[0]);
  return WG_CELLS[key];
}

function validPhase([done, total]) {
  return Number.isInteger(done) && Number.isInteger(total) && total > 0 && done >= 0 ? [Math.min(done, total), total] : null;
}

export function parsePhase(phases) {
  if (Array.isArray(phases)) return validPhase(phases);
  const match = /^(\d+)\/(\d+)$/.exec(String(phases ?? ''));
  if (!match) return null;
  return validPhase([Number(match[1]), Number(match[2])]);
}

export function currentCell(phase) {
  const [done, total] = phase ?? [];
  if (!(total > 0) || !(done >= 0)) return null;
  return WG_ORDER[Math.min(2, Math.floor((3 * done) / total))];
}

export function wgState({ state, pulse, outlined, unfolded }) {
  if (WG_STATES.includes(state)) return state;
  if (unfolded || outlined) return 'paused';
  if (pulse) return 'running';
  return 'idle';
}

export function leadCell(phase, cell) {
  return cell || currentCell(phase) || 'top';
}

export function turnKey(state, phase, cell) {
  if (state === 'running') return currentCell(phase) ? `running-${currentCell(phase)}` : 'idle';
  if (state === 'failed') return `failed-${leadCell(phase, cell)}`;
  if (state === 'needs' || state === 'queued') return state;
  return 'idle';
}

export function wgPose(state, key, px) {
  if (WG_FRONTAL.includes(state)) return [0, 0, 0];
  const k = px > MARK_SIZES.row ? 1 : TURN.smallTurn;
  return (WG_STILLS[key] ?? WG_STILLS.idle).map((a) => a * k);
}

export function wgLive(state, key, px, reduced) {
  return !reduced && px > MARK_SIZES.row && !WG_FRONTAL.includes(state) && !!WG_TURNS[key];
}

export function wgTrack(key) {
  const spec = WG_TURNS[key];
  return spec ? { dur: spec.dur, times: spec.frames.map((f) => f[0]), values: spec.frames.map((f) => f.slice(1)) } : null;
}

export function cellPaint({ name, index, state, phase, cell, hub, neutral, danger, px }) {
  const thin = px < SMALL;
  const pop = px > MARK_SIZES.row;
  const dash = { strokeWidth: thin ? 5.5 : 3.6, strokeDasharray: thin ? '8 6' : '6.5 5', strokeLinecap: 'round' };
  const ring = { fill: 'none', stroke: neutral, strokeWidth: thin ? WG_RING[0] : WG_RING[1] };
  const faint = { fill: neutral, fillOpacity: WG_ALPHA.faint };
  const lead = name === leadCell(phase, cell);
  if (state === 'paused') return { fill: 'none', stroke: neutral, ...dash };
  if (state === 'queued') return ring;
  if (state === 'offline') return { fill: neutral, fillOpacity: WG_ALPHA.offline };
  if (state === 'failed') return lead ? { fill: danger } : faint;
  if (state === 'needs') return lead ? { fill: hub, pop } : { fill: neutral };
  if (state === 'running' && currentCell(phase)) {
    const k = WG_ORDER.indexOf(currentCell(phase));
    if (index < k) return faint;
    if (index === k) return { fill: hub, track: 'fill' };
    return ring;
  }
  if (state === 'running') return { fill: hub, fillOpacity: name === 'top' ? 1 : WG_ALPHA.chase, track: 'chase', lag: CHASE_LAG * index };
  return { fill: neutral };
}

export { WG_ORDER };
