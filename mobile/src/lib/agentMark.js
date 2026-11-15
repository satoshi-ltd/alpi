import { BRAND_INK, shapeOf, TWIN_SHAPE } from '../../../common/shapes.mjs';
import { EXPRESSIONS, EYE_CAP, EYE_GAP_PX, EYE_MIN_PX, EYE_PILL_HALF, MARK_SIZES, MOTION_MIN, SEQUENCE, SHAPES, SMALL, STILL, TURN, TURN_CSS } from '../../../common/agentMarks.mjs';
import { markTone } from '../../../common/markTone.mjs';

export const FLAT_STATES = ['paused', 'offline'];
export const OUTLINED_STATES = ['paused'];
export const MARK_STATES = ['idle', 'busy', 'working', 'needs', 'done', 'failed', 'paused', 'offline'];
export const OFFLINE_OPACITY = 0.3;
const SPLINE = [0.45, 0, 0.25, 1];

export function markName(shape, px) {
  const id = shapeOf(shape);
  if (id === TWIN_SHAPE) return px < 24 ? 'alpi-twin-small' : 'alpi-twin';
  return SHAPES[id] ? id : 'round';
}

export function markFill({ id, color, mode, fallback }) {
  if (shapeOf(id) === TWIN_SHAPE) return BRAND_INK[mode === 'dark' ? 'dark' : 'light'];
  return /^#[0-9a-f]{6}$/i.test(color ?? '') ? markTone(color, mode === 'dark' ? 'dark' : 'light') : fallback;
}

export function stateFrom({ state, pulse, outlined, unfolded }) {
  if (MARK_STATES.includes(state)) return state;
  if (outlined) return 'needs';
  if (unfolded) return 'paused';
  if (pulse) return 'working';
  return 'idle';
}

export function stillPose(state, px) {
  const pose = TURN.still[state];
  if (!pose || FLAT_STATES.includes(state)) return [0, 0, 0];
  const k = px > MARK_SIZES.row ? 1 : TURN.smallTurn;
  return pose.map((a) => a * k);
}

export function delayFor(seed) {
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return (h % 96) / 10;
}

export function animates(state, px, reduced) {
  return !reduced && px >= MOTION_MIN && !!SEQUENCE[state] && (state !== 'idle' || px >= SMALL);
}

export function turnsLive(state, px) {
  return px > MARK_SIZES.row && TURN.live.includes(state) && !!TURN_TRACKS[state];
}

export function eyePair(spec, size, key) {
  const [, gx, gy, left, right] = key;
  const reach = size < SMALL ? 0.7 : 1;
  const grow = Math.min(EYE_CAP, Math.max(1, (EYE_MIN_PX * 50) / (EYE_PILL_HALF * size)));
  const gap = Math.max(3, (EYE_GAP_PX * 100) / size) / 2;
  const flat = [];
  for (const [side, [name, s, dy]] of [[-1, left], [1, right]]) {
    const pts = EXPRESSIONS[name];
    const inner = -Math.min(...pts.map((p) => p[0]));
    const scale = inner > 0 ? Math.min(grow * s, (spec.eyeDx - gap) / inner) : grow * s;
    const x0 = spec.eyeX + reach * gx + side * spec.eyeDx;
    const y0 = spec.eyeY + reach * (gy + dy);
    for (const [x, y] of pts) flat.push(x0 + side * x * scale, y0 + y * scale);
  }
  return flat;
}

export function parallax(pose) {
  'worklet';
  const sy = Math.sin((pose[0] * Math.PI) / 180);
  const sx = Math.sin((pose[1] * Math.PI) / 180);
  return [TURN.slide[0] * sy, -TURN.slide[1] * sx, 1 - TURN.squeeze * Math.abs(sy), 1 - TURN.squeeze * Math.abs(sx)];
}

export function eyesPath(flat, spec, shift) {
  'worklet';
  const [tx, ty, sx, sy] = shift;
  const half = flat.length / 2;
  let d = '';
  for (let i = 0; i < flat.length; i += 2) {
    const x = spec.eyeX + (flat[i] - spec.eyeX) * sx + tx;
    const y = spec.eyeY + (flat[i + 1] - spec.eyeY) * sy + ty;
    d += `${i === 0 || i === half ? (i ? 'Z M' : 'M') : ' '}${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return `${d}Z`;
}

function bez(a, b, t) {
  'worklet';
  return 3 * a * t * (1 - t) * (1 - t) + 3 * b * t * t * (1 - t) + t * t * t;
}

export function ease(x) {
  'worklet';
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  let lo = 0;
  let hi = 1;
  let t = x;
  for (let i = 0; i < 18; i += 1) {
    const v = bez(SPLINE[0], SPLINE[2], t);
    if (Math.abs(v - x) < 1e-4) break;
    if (v < x) lo = t;
    else hi = t;
    t = (lo + hi) / 2;
  }
  return bez(SPLINE[1], SPLINE[3], t);
}

function segment(times, p) {
  'worklet';
  let i = 0;
  while (i < times.length - 2 && times[i + 1] <= p) i += 1;
  const span = times[i + 1] - times[i];
  return [i, span > 0 ? ease((p - times[i]) / span) : 0];
}

export function sampleTrack(track, seconds) {
  'worklet';
  const p = (((seconds % track.dur) + track.dur) % track.dur) / track.dur;
  const [i, k] = segment(track.times, p);
  const a = track.values[i];
  const b = track.values[i + 1];
  const out = new Array(a.length);
  for (let j = 0; j < a.length; j += 1) out[j] = a[j] + (b[j] - a[j]) * k;
  return out;
}

export function eyeTrack(spec, size, state) {
  const seq = SEQUENCE[state];
  if (!seq) return null;
  return { dur: seq.dur, times: seq.keys.map((key) => key[0]), values: seq.keys.map((key) => eyePair(spec, size, key)) };
}

export function stillEyes(spec, size, state) {
  return eyePair(spec, size, STILL[state] ?? STILL.idle);
}

function parseTurns(css) {
  const tracks = {};
  const re = /@keyframes vt-turn-([a-z]+)\{(.*?\})\}/g;
  const durations = {};
  for (const [, name, secs] of css.matchAll(/\.vt-turn-([a-z]+)\{animation-name: vt-turn-[a-z]+; animation-duration: ([\d.]+)s\}/g)) durations[name] = Number(secs);
  for (const [, name, body] of css.matchAll(re)) {
    const frames = [];
    for (const [, stops, ry, rx, rz] of body.matchAll(/([\d%,]+)\{transform: rotateY\((-?[\d.]+)deg\) rotateX\((-?[\d.]+)deg\) rotateZ\((-?[\d.]+)deg\)\}/g)) {
      for (const stop of stops.split(',')) frames.push([Number(stop.replace('%', '')) / 100, [Number(ry), Number(rx), Number(rz)]]);
    }
    frames.sort((a, b) => a[0] - b[0]);
    if (durations[name] && frames.length > 1) tracks[name] = { dur: durations[name], times: frames.map((f) => f[0]), values: frames.map((f) => f[1]) };
  }
  return tracks;
}

export const TURN_TRACKS = parseTurns(TURN_CSS);

function gcd(a, b) {
  return b ? gcd(b, a % b) : a;
}

export function loopSeconds(...durations) {
  const tenths = durations.filter(Boolean).map((d) => Math.round(d * 10));
  if (!tenths.length) return 0;
  return tenths.reduce((a, b) => (a * b) / gcd(a, b)) / 10;
}

export function markRotation(pose, px) {
  'worklet';
  return [{ perspective: px * TURN.depth }, { rotateY: `${pose[0]}deg` }, { rotateX: `${pose[1]}deg` }, { rotateZ: `${pose[2]}deg` }];
}

export function shapeBox(name) {
  const nums = SHAPES[name].d.match(/-?[\d.]+/g).map(Number);
  const xs = nums.filter((_, i) => i % 2 === 0);
  const ys = nums.filter((_, i) => i % 2 === 1);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

export { SHAPES, STILL };
