import { ACCENTS, ACCENT_SHAPES } from '../../common/accents.mjs';
import { BODY, LOOK, MARK_SIZES, MOTION_CSS, MOTION_MIN, POSE, SHAPES, STILL, TURN, TURN_CSS } from '../../common/agentMarks.mjs';
import { eyePair, eyePath } from '../../common/markEyes.mjs';
import { NAME_FONT, nameTone } from '../../common/name.mjs';
import { markTone, toneAgainst } from '../../common/markTone.mjs';
import { WG_ALPHA, WG_CELLS, WG_ORDER, WG_STILLS } from '../../common/workgroupMark.mjs';
import { workgroupGap } from '../../common/workgroupMarkState.mjs';
import { palettes } from '../../common/tokens.mjs';

export const NIGHT = palettes.dark.bg;
export const PAPER = palettes.light.bg;
export const CREAM = '#f3efe6';
export const INK = '#14110c';
export const CARD_GROUND = '#ffffff';
export const EYE_PAPER = palettes.light.markEye;
export const EYE_NIGHT = palettes.dark.markEye;
export const FAVICON_INK = '#14110c';
export const FAVICON_CREAM = '#f3efe6';
export const FONT_FILE = 'bricolage-800-latin.woff2';
export const FONT_URL = `assets/fonts/${FONT_FILE}`;
export const TAGLINE = 'Your private agent network.';
export const TWIN = 'alpi-twin';
export const TWIN_SMALL = 'alpi-twin-small';
export const SMALL_BELOW = 24;
export const HALF_TURN = 0.5;
export const FAVICON_FILL = 0.92;
export const AGENTS_FLOOR = 3;
export const AGENTS_BAND_EM = 1.5;
export const AGENTS_TILE_EM = AGENTS_BAND_EM * ACCENTS.length;
export const AGENTS_PASS_S = 24;

const TURN_ORIGIN = [50, 55];

export const IDENTITIES = ACCENTS.map(([colour, hex]) => {
  const shape = ACCENT_SHAPES[colour];
  return { colour, hex, shape, name: `${colour} ${shape}` };
});

const fixed = (n) => Number(n.toFixed(2));
const f2 = (n) => n.toFixed(2);
const a11y = (label) => (label ? `role="img" aria-label="${label}"` : 'aria-hidden="true" focusable="false"');

export const heldPose = () => TURN.still.idle.slice();
export const halfPose = () => heldPose().map((a) => a * HALF_TURN);
const twinShape = (size) => (size < SMALL_BELOW ? TWIN_SMALL : TWIN);

function knots(shape) {
  const numbers = SHAPES[shape].d.match(/-?\d+(?:\.\d+)?/g).map(Number);
  const points = [];
  for (let i = 0; i + 1 < numbers.length; i += 2) points.push([numbers[i], numbers[i + 1]]);
  const out = [points[0], ...points.filter((_, i) => i >= 3 && (i - 3) % 3 === 0)];
  const [first, last] = [out[0], out.at(-1)];
  return last[0] === first[0] && last[1] === first[1] ? out.slice(0, -1) : out;
}

function project(points, pose) {
  const [ry, rx, rz] = pose.map((a) => (a * Math.PI) / 180);
  const [ox, oy] = TURN_ORIGIN;
  return points.map(([x, y]) => {
    let [px, py, pz] = [x - ox, y - oy, 0];
    [px, py] = [px * Math.cos(rz) - py * Math.sin(rz), px * Math.sin(rz) + py * Math.cos(rz)];
    [py, pz] = [py * Math.cos(rx) - pz * Math.sin(rx), py * Math.sin(rx) + pz * Math.cos(rx)];
    [px, pz] = [px * Math.cos(ry) + pz * Math.sin(ry), -px * Math.sin(ry) + pz * Math.cos(ry)];
    const w = 1 - pz / (100 * TURN.depth);
    return [50 + (px + ox - 50) / w, 50 + (py + oy - 50) / w];
  });
}

export function twinParts(size, pose) {
  const shape = twinShape(size);
  const spec = SHAPES[shape];
  const body = project(knots(shape), pose);
  const ox = spec.eyeX + POSE.idle.shift;
  const oy = spec.eyeY + POSE.idle.lift;
  const [sy, sx] = [Math.sin((pose[0] * Math.PI) / 180), Math.sin((pose[1] * Math.PI) / 180)];
  const slide = [TURN.slide[0] * sy, -TURN.slide[1] * sx];
  const squeeze = [1 - TURN.squeeze * Math.abs(sy), 1 - TURN.squeeze * Math.abs(sx)];
  const eyes = eyePair(spec, size).map((eye) => project(eye.map(([x, y]) => [ox + slide[0] + (x - ox) * squeeze[0], oy + slide[1] + (y - oy) * squeeze[1]]), pose));
  return { body, eyes };
}

function bezier(points) {
  const n = points.length;
  const dist = (a, b) => Math.max(Math.hypot(a[0] - b[0], a[1] - b[1]), 1e-6) ** 0.5;
  return points.map((p1, i) => {
    const p0 = points[(i - 1 + n) % n];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];
    const [d1, d2, d3] = [dist(p0, p1), dist(p1, p2), dist(p2, p3)];
    const c1 = [0, 1].map((k) => (d1 * d1 * p2[k] - d2 * d2 * p0[k] + (2 * d1 * d1 + 3 * d1 * d2 + d2 * d2) * p1[k]) / (3 * d1 * (d1 + d2)));
    const c2 = [0, 1].map((k) => (d3 * d3 * p1[k] - d2 * d2 * p3[k] + (2 * d3 * d3 + 3 * d3 * d2 + d2 * d2) * p2[k]) / (3 * d3 * (d3 + d2)));
    return [p1, c1, c2, p2];
  });
}

export function bounds(points) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return { left: Math.min(...xs), right: Math.max(...xs), top: Math.min(...ys), bottom: Math.max(...ys) };
}

export function twinPath({ body, eyes }, place = (p) => p) {
  const pt = (p) => place(p).map(f2).join(' ');
  return `M${pt(body[0])}${bezier(body).map(([, c1, c2, p]) => ` C${pt(c1)} ${pt(c2)} ${pt(p)}`).join('')} Z${eyes.map((eye) => `M${eye.map(pt).join(' ')}Z`).join('')}`;
}

export function twinMark({ height = 64, className = '', label = '', pose = halfPose(), fill = '', size = 100, cut = false } = {}) {
  const parts = twinParts(size, pose);
  const box = bounds(parts.body);
  const [w, h] = [box.right - box.left + 2, box.bottom - box.top + 2];
  const viewBox = `${f2(box.left - 1)} ${f2(box.top - 1)} ${f2(w)} ${f2(h)}`;
  const cls = className ? ` class="${className}"` : '';
  const paint = fill ? ` fill="${fill}"` : '';
  const art = cut
    ? `<path d="${twinPath(parts)}"${paint} fill-rule="evenodd"/>`
    : `<path class="mark-body" d="${twinPath({ body: parts.body, eyes: [] })}"${paint}/>${eyesPath(parts.eyes)}`;
  return `<svg xmlns="http://www.w3.org/2000/svg"${cls} viewBox="${viewBox}" width="${fixed((height * w) / h)}" height="${height}" ${a11y(label)}>${art}</svg>`;
}

function eyesPath(eyes) {
  return `<path class="mark-eye" d="${eyes.map((eye) => `M${eye.map((p) => p.map(f2).join(' ')).join(' ')}Z`).join('')}" fill="${EYE_NIGHT}"/>`;
}

export function favicon() {
  const parts = twinParts(100, halfPose());
  const box = bounds(parts.body);
  const scale = (FAVICON_FILL * 100) / Math.max(box.right - box.left, box.bottom - box.top);
  const [cx, cy] = [(box.left + box.right) / 2, (box.top + box.bottom) / 2];
  const place = ([x, y]) => [50 + scale * (x - cx), 50 + scale * (y - cy)];
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="64" height="64" role="img" aria-label="alpi"><style>path{fill:${FAVICON_INK}}@media (prefers-color-scheme: dark){path{fill:${FAVICON_CREAM}}}</style><path d="${twinPath(parts, place)}" fill="${FAVICON_INK}" fill-rule="evenodd"/></svg>`;
}

export function shapeMark({ shape, hex, name, size = 34, label = true }) {
  const spec = SHAPES[shape];
  if (!spec || shape === TWIN || shape === TWIN_SMALL) throw new Error(`no profile shape "${shape}"`);
  const eyes = eyePair(spec, size).map((eye) => `M${eye.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')}Z`).join('');
  const named = label ? `role="img" aria-label="${name}"><title>${name}</title>` : `${a11y('')} data-shape="${shape}">`;
  return `<svg viewBox="0 0 100 100" width="${size}" height="${size}" ${named}${bodyPath(spec.d, hex)}<path class="mark-eye" d="${eyes}" fill="${EYE_NIGHT}"/></svg>`;
}

const identityFor = (shape) => {
  const identity = IDENTITIES.find((item) => item.shape === shape);
  if (!identity) throw new Error(`no identity wears the shape "${shape}"`);
  return identity;
};

export function pairMark(shape, size = 24, label = true) {
  return shapeMark({ ...identityFor(shape), size, label });
}

export const nameStyle = (hex) => `--name-night:${nameTone(hex, NIGHT)};--name-paper:${nameTone(hex, PAPER)}`;

export function displayName(shape, name) {
  return `<span class="display display-name" style="${nameStyle(identityFor(shape).hex)}">${name}</span>`;
}

export function profileName(shape, name, size = 18, state = '') {
  const mark = state ? liveMark({ shape, state, size }) : pairMark(shape, size, false);
  return `<span class="profile-name">${mark}${displayName(shape, name)}</span>`;
}

export function liveMark({ shape, state = 'idle', size, seed = `${shape}-${state}-${size}` }) {
  const fill = shape === TWIN ? 'var(--brand-ink)' : identityFor(shape).hex;
  return `<span class="live-mark" style="--size:${size}px" aria-hidden="true">${castMark({ shape, fill, state, seed, size })}</span>`;
}

export function familyRow(size = 20) {
  return `<span class="family" aria-hidden="true">${IDENTITIES.map(({ shape }) => pairMark(shape, size, false)).join('')}</span>`;
}

export const HONEYCOMB_STATE = 'running-top';

export function honeycomb(shape, size = 44) {
  const want = workgroupGap(size);
  const gap = Object.keys(WG_CELLS).map(Number).reduce((best, g) => (Math.abs(g - want) < Math.abs(best - want) ? g : best));
  const cells = WG_CELLS[gap.toFixed(1)];
  const lead = WG_ORDER.indexOf('top');
  const hex = identityFor(shape).hex;
  const art = WG_ORDER.map((name, i) => {
    if (i < lead) return `<path data-cell="${name}" d="${cells[name]}" class="wg-faint" fill-opacity="${WG_ALPHA.faint}"/>`;
    if (i === lead) return `<path data-cell="${name}" data-lead="" d="${cells[name]}" fill="${hex}"/>`;
    return `<path data-cell="${name}" d="${cells[name]}" class="wg-ring" fill="none" stroke-width="4.5"/>`;
  }).join('');
  return `<span class="live-mark" style="--size:${size}px" aria-hidden="true"><svg viewBox="0 0 100 100" focusable="false" data-mark="soft-honeycomb" data-state="running" style="transform:${rotation(WG_STILLS[HONEYCOMB_STATE])}">${art}</svg></span>`;
}

export function twinBadge(height = 40) {
  return twinMark({ height, className: 'twin-mark', pose: heldPose() });
}

export function demoProfiles(byName, size = 13) {
  return Object.fromEntries(Object.entries(byName).map(([name, shape]) => {
    const identity = identityFor(shape);
    return [name, { color: identity.hex, mark: shapeMark({ ...identity, size }) }];
  }));
}

export const LOGO_LOOK = { turnX: 21.6, turnY: 14.4, eyeX: 6, eyeY: 4 };

export function lockup({ height = 34, live = false } = {}) {
  const mark = twinMark({ height, className: 'logo-mark' });
  return `<span class="logo">${live ? `<span class="logo-gaze">${mark}</span>` : mark}<span class="logo-word display">alpi</span></span>`;
}

export const heroTone = (hex, ground) => toneAgainst(hex, ground, AGENTS_FLOOR);

export function agentTones() {
  return { night: ACCENTS.map(([, hex]) => markTone(hex, 'dark')), paper: ACCENTS.map(([, hex]) => markTone(hex, 'light')) };
}

function bodyPath(d, fill) {
  const paper = markTone(fill, 'light');
  return paper === fill ? `<path class="mark-body" d="${d}" fill="${fill}"/>` : `<path class="mark-body mark-toned" d="${d}" fill="${fill}" style="--mark-paper:${paper}"/>`;
}

const stopAt = (i, of) => Number(((i / of) * 100).toFixed(4));
export const flowGradient = (tones) => `linear-gradient(90deg,${[...tones, tones[0]].map((tone, i) => `${tone} ${stopAt(i, tones.length)}%`).join(',')})`;
export const stillGradient = (tones) => `linear-gradient(90deg,${tones.map((tone, i) => `${tone} ${stopAt(i, tones.length - 1)}%`).join(',')})`;

function agentsCss() {
  const tones = agentTones();
  const word = '.hero h1 .display-agents';
  const vars = (ground) => `--agents-ink:${tones[ground][0]};--agents-still:${stillGradient(tones[ground])};--agents-flow:${flowGradient(tones[ground])}`;
  return [
    `${word}{${vars('night')};color:var(--agents-ink);padding:.12em .06em;margin:-.12em -.06em}`,
    `:root[data-theme="light"] ${word}{${vars('paper')}}`,
    `@supports (-webkit-background-clip:text) or (background-clip:text){${word}{background:var(--agents-still);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent}}`,
    `@keyframes agents-flow{from{background-position:0 0}to{background-position:-${AGENTS_TILE_EM}em 0}}`,
    `@media (prefers-reduced-motion:no-preference){@supports (-webkit-background-clip:text) or (background-clip:text){${word}{background-image:var(--agents-flow);background-size:${AGENTS_TILE_EM}em 100%;background-repeat:repeat-x;animation:agents-flow ${AGENTS_PASS_S}s linear infinite}${word.replace('.hero', '.hero.is-away')}{animation-play-state:paused}}}`,
  ];
}

export function brandCss() {
  return [
    `@font-face{font-family:"${NAME_FONT}";font-style:normal;font-weight:800;font-display:swap;src:url("${FONT_URL}") format("woff2")}`,
    `:root{--brand-ink:${CREAM}}`,
    `:root[data-theme="light"]{--brand-ink:${INK}}`,
    `.mark-eye{fill:var(--mark-eye,${EYE_NIGHT})}`,
    `:root[data-theme="light"] .mark-toned{fill:var(--mark-paper)}`,
    `.logo .logo-word.display,.hero h1 .display,h1.display-heading,h2.display-heading,.display-name{font-family:"${NAME_FONT}",Geist,system-ui,sans-serif}`,
    `.display{font-weight:800;letter-spacing:-.04em;color:var(--brand-ink);display:inline-block}`,
    `.logo-mark .mark-body{fill:var(--brand-ink)}`,
    `.logo-gaze{display:inline-flex;perspective:96px}`,
    `.logo-gaze .logo-mark{transform-origin:50% 55%;transform:rotateY(calc(var(--gx, 0) * ${LOGO_LOOK.turnX}deg)) rotateX(calc(var(--gy, 0) * -${LOGO_LOOK.turnY}deg))}`,
    `.logo-gaze .mark-eye{transform:translate(calc(var(--gx, 0) * ${LOGO_LOOK.eyeX}px), calc(var(--gy, 0) * ${LOGO_LOOK.eyeY}px))}`,
    `:root .logo .logo-word.display{color:var(--brand-ink);font-weight:800;letter-spacing:-.04em}`,
    `.hero h1 .display{display:block;width:fit-content}`,
    `.profile-name{display:inline-flex;align-items:center;gap:.45em;vertical-align:middle}`,
    `.profile-name svg{flex:none;display:block}`,
    `.twin-mark .mark-body{fill:var(--brand-ink)}`,
    `.mark-rest{stroke:var(--muted)}`,
    `.mark-rest-eye{fill:var(--muted)}`,
    `.wg-faint{fill:var(--muted)}`,
    `.wg-ring{stroke:var(--muted)}`,
    `.family{display:inline-flex;flex-wrap:wrap;align-items:center;gap:10px}`,
    `.family svg{display:block;flex:none}`,
    `.live-mark{display:inline-flex;flex:none;width:var(--size);height:var(--size);perspective:calc(var(--size) * 2.6)}`,
    `.live-mark svg{display:block;width:100%;height:100%;overflow:visible;transform-origin:50% 55%}`,
    `.display-name{color:var(--name-night)}`,
    `:root[data-theme="light"] .display-name{color:var(--name-paper)}`,
    ...agentsCss(),
    `.hero h1 .hero-line{display:flex;column-gap:.24em}`,
    `h1.display-heading{display:block;width:fit-content;max-width:100%;padding:0 0 .12em;line-height:1.08}`,
    `h2.display-heading{display:block;width:fit-content;margin:15px 0 25px;padding:0 0 .12em;line-height:1.1}`,
    `@media (forced-colors:active){.display,.display-name,.hero h1 .display-agents{color:CanvasText;-webkit-text-fill-color:CanvasText;background:none;animation:none}.logo-mark .mark-body{fill:CanvasText}.mark-eye{fill:Canvas}}`,
    `@media print{.display,.display-name,.hero h1 .display-agents{color:#000;-webkit-text-fill-color:#000;background:none;animation:none}.logo-mark .mark-body{fill:#000}.mark-toned{fill:var(--mark-paper)}.mark-eye{fill:#fff}}`,
    '',
  ].join('\n');
}

const WORD_WIDTH = 1.45;

export function cardSvg({ width = 1200, height = 630, fontData = '' } = {}) {
  const parts = twinParts(100, heldPose());
  const box = bounds(parts.body);
  const markHeight = Math.round(height * 0.5);
  const k = markHeight / (box.bottom - box.top);
  const markWidth = (box.right - box.left) * k;
  const fontSize = Math.round(markHeight * 0.66);
  const gap = Math.round(markHeight * 0.3);
  const top = Math.round((height - markHeight) / 2);
  const left = Math.round((width - (markWidth + gap + fontSize * WORD_WIDTH)) / 2);
  const baseline = top + Math.round(markHeight * 0.9);
  const place = ([x, y]) => [left + (x - box.left) * k, top + (y - box.top) * k];
  const font = fontData
    ? `<style>@font-face{font-family:"${NAME_FONT}";font-weight:800;src:url(data:font/woff2;base64,${fontData}) format("woff2")}</style>`
    : '';
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="alpi — ${TAGLINE.toLowerCase().replace(/\.$/, '')}">`,
    font,
    `<rect width="${width}" height="${height}" fill="${CARD_GROUND}"/>`,
    `<path d="${twinPath(parts, place)}" fill="${INK}" fill-rule="evenodd"/>`,
    `<text x="${fixed(left + markWidth + gap)}" y="${baseline}" font-family="${NAME_FONT}, Geist, Arial Black, sans-serif" font-size="${fontSize}" font-weight="800" letter-spacing="${fixed(-0.04 * fontSize)}" fill="${INK}">alpi</text>`,
    '</svg>',
    '',
  ].join('');
}

export const THEME_COLOR = { light: palettes.light.bg, dark: palettes.dark.bg };

export function themeScript(template) {
  return template.replace("'__THEME_LIGHT__'", JSON.stringify(THEME_COLOR.light)).replace("'__THEME_DARK__'", JSON.stringify(THEME_COLOR.dark));
}

export function thumbnailSvg({ size = 400 } = {}) {
  const mark = twinMark({ height: Math.round(size * 0.42), pose: heldPose(), fill: INK, cut: true });
  const art = mark.replace('<svg xmlns="http://www.w3.org/2000/svg"', `<svg x="0" y="${Math.round(size * 0.14)}" width="${size}"`).replace(/ width="[\d.]+" height=/, ' height=');
  return `<svg viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg"><rect width="${size}" height="${size}" fill="${PAPER}"/>${art}<text x="${size / 2}" y="${Math.round(size * 0.8)}" text-anchor="middle" fill="${INK}" font-family="${NAME_FONT}, Geist, sans-serif" font-size="${Math.round(size * 0.16)}" font-weight="800" letter-spacing="${fixed(-0.04 * size * 0.16)}">alpi</text></svg>`;
}

export const CAST_DRAW = 72;
export const STATE_NAMES = { idle: 'idle', busy: 'thinking', working: 'working', needs: 'needs you', done: 'done', failed: 'failed', paused: 'paused' };
export const CAST = [
  { shape: 'round', role: 'scout', state: 'working', lift: 0.12 },
  { shape: 'squircle', role: 'lens', state: 'needs', lift: -0.21 },
  { shape: 'drop', role: 'scribe', state: 'done', lift: 0.17 },
  { shape: 'dome', role: 'ledger', state: 'idle', lift: -0.07 },
  { shape: 'pill', role: 'builder', state: 'working', lift: 0.24 },
  { shape: 'clover', role: 'researcher', state: 'busy', lift: -0.14 },
  { shape: 'cloud', role: 'tutor', state: 'paused', lift: 0.1 },
  { shape: 'bean', role: 'curator', state: 'working', lift: -0.24 },
  { shape: 'pebble', role: 'librarian', state: 'done', lift: 0.14 },
  { shape: 'arch', role: 'sentinel', state: 'failed', lift: -0.05 },
  { shape: 'heart', role: 'planner', state: 'needs', lift: 0.21 },
  { shape: 'bell', role: 'reviewer', state: 'idle', lift: -0.12 },
];
export const CAST_TWIN = { role: 'alpi', state: 'idle' };

const POINTER_TURN = /\.vt:has\(\.vt-q\d:hover\) \.vt-held\{[^}]*\}/g;

function delayFor(seed) {
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return -(h % 96) / 10;
}

const rotation = ([ry, rx, rz]) => `rotateY(${ry}deg) rotateX(${rx}deg) rotateZ(${rz}deg)`;

function parallax([ry, rx]) {
  const sy = Math.sin((ry * Math.PI) / 180);
  const sx = Math.sin((rx * Math.PI) / 180);
  return `translate(${f2(TURN.slide[0] * sy)}px, ${f2(-TURN.slide[1] * sx)}px) scale(${(1 - TURN.squeeze * Math.abs(sy)).toFixed(3)}, ${(1 - TURN.squeeze * Math.abs(sx)).toFixed(3)})`;
}

export function castMark({ shape, fill, state, seed = shape, size = CAST_DRAW, look = false }) {
  const spec = SHAPES[shape];
  if (!spec) throw new Error(`no mark shape "${shape}"`);
  const live = size >= MOTION_MIN && TURN.live.includes(state);
  const pose = (TURN.still[state] ?? [0, 0, 0]).map((a) => (size > MARK_SIZES.row ? a : a * TURN.smallTurn));
  const lean = POSE[state] ?? POSE.idle;
  const origin = `transform-origin:${f2(spec.eyeX + lean.shift)}px ${f2(spec.eyeY + lean.lift)}px`;
  const eyes = eyePair(spec, size, STILL[state] ?? STILL.idle).map(eyePath).join('');
  let art;
  if (state === 'paused') {
    art = `<path class="mark-rest" d="${spec.d}" fill="none" stroke-width="3.6" stroke-dasharray="6.5 5" stroke-linecap="round"/><path class="mark-rest-eye" d="${eyes}"/>`;
  } else {
    const eyeArt = live && LOOK[state] ? `<g class="am-a am-lid-${LOOK[state]}" style="${origin}"><path class="mark-eye" d="${eyes}"/></g>` : `<path class="mark-eye" d="${eyes}"/>`;
    const lid = look ? `<g class="cast-look">${eyeArt}</g>` : eyeArt;
    art = `${bodyPath(spec.d, fill)}<g class="${live ? `vt-a vt-eyes-${state}` : 'cast-eyes'}" style="${origin};transform:${parallax(pose)}">${lid}</g>`;
    if (live && BODY[state]) art = `<g class="am-a am-body-${BODY[state]}" style="--s:${spec.stretch};--w:${spec.wobble};transform-origin:50px ${spec.originY}px">${art}</g>`;
  }
  const turn = live ? ` class="vt-a vt-turn-${state}"` : '';
  return `<svg${turn} viewBox="0 0 100 100" aria-hidden="true" focusable="false" data-shape="${shape}" data-state="${state}" style="--d:${delayFor(seed)}s;transform:${rotation(pose)}">${art}</svg>`;
}

function castItem({ mark, label, name, tone, state, lift, kind, edge, first }) {
  const tip = `<span class="cast-tip" aria-hidden="true"><span class="display-name"${tone}>${name}</span> · ${STATE_NAMES[state]}</span>`;
  const cls = ['cast-item', kind, edge].filter(Boolean).join(' ');
  return `<span class="${cls}" tabindex="${first ? 0 : -1}" role="img" aria-label="${label}" style="--lift:${lift}">${mark}${tip}</span>`;
}

const CAST_KEYS = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };

function wireCast(keys) {
  const cast = document.querySelector('.cast');
  if (!cast) return;
  const items = [...cast.querySelectorAll('.cast-item')];
  cast.addEventListener('keydown', (e) => {
    const at = items.indexOf(document.activeElement);
    if (at < 0) return;
    let to = null;
    if (e.key in keys) to = (at + keys[e.key] + items.length) % items.length;
    if (e.key === 'Home') to = 0;
    if (e.key === 'End') to = items.length - 1;
    if (to === null) return;
    e.preventDefault();
    items[at].tabIndex = -1;
    items[to].tabIndex = 0;
    items[to].focus();
  });
}

export function castScript() {
  return `(${wireCast.toString()})(${JSON.stringify(CAST_KEYS)});`;
}

const PHONE_START = new Set([0, 4, 8]);
const PHONE_END = new Set([3, 7, 11]);

export function castHtml() {
  const items = CAST.map(({ shape, role, state, lift }, i) => {
    const { hex } = identityFor(shape);
    const edge = [i === 0 ? 'cast-first' : '', i === CAST.length - 1 ? 'cast-last' : '', PHONE_START.has(i) ? 'cast-start' : '', PHONE_END.has(i) ? 'cast-end' : ''].filter(Boolean).join(' ');
    return castItem({
      mark: castMark({ shape, fill: hex, state, seed: `cast-${shape}` }),
      label: `${role} · ${STATE_NAMES[state]}`,
      name: role,
      tone: ` style="--name-night:${nameTone(hex, NIGHT)};--name-paper:${nameTone(hex, PAPER)}"`,
      state,
      lift,
      kind: i === 4 || i === 5 || i === 6 || i === 7 ? 'cast-middle' : '',
      edge,
      first: i === 0,
    });
  });
  const twin = castItem({
    mark: `<span class="cast-gaze">${castMark({ shape: TWIN, fill: 'var(--brand-ink)', state: CAST_TWIN.state, seed: 'cast-twin', look: true })}</span>`,
    label: `${CAST_TWIN.role} · ${STATE_NAMES[CAST_TWIN.state]}`,
    name: CAST_TWIN.role,
    tone: ' style="--name-night:var(--brand-ink);--name-paper:var(--brand-ink)"',
    state: CAST_TWIN.state,
    lift: 0,
    kind: 'cast-twin',
  });
  const brk = '<span class="cast-break" aria-hidden="true"></span>';
  return `<div class="cast" role="group" aria-label="Twelve profiles and alpi, each in a state. Use the arrow keys to move between them.">${items.slice(0, 4).join('')}${brk}${items.slice(4, 6).join('')}${twin}${items.slice(6, 8).join('')}${brk}${items.slice(8).join('')}</div>`;
}

export function castCss() {
  return [
    MOTION_CSS,
    TURN_CSS.replace(POINTER_TURN, ''),
    '.is-away .am-a,.is-away .vt-a{animation-play-state:paused}',
    '@media (prefers-reduced-motion:reduce){.am-a,.vt-a{animation:none}}',
  ].join('\n');
}


export const STATE_ROWS = [
  { role: 'builder', state: 'working', label: 'working · on PR #412', line: 'Squints at the task. The row says what it is doing.' },
  { role: 'lens', state: 'needs', label: 'needs you', line: 'Eyes wide. An approval or a question waits, counted on the badge.' },
  { role: 'scribe', state: 'done', label: 'done · 2m', line: 'Happy until you read the reply. The notification carries it.' },
  { role: 'sentinel', state: 'failed', label: 'failed', line: 'Sad eyes. The notification says why.' },
  { role: 'tutor', state: 'paused', label: 'paused', line: 'A dashed outline, asleep. Its schedules wait; its history stays.' },
];

export function statesHtml(size = 52) {
  const rows = STATE_ROWS.map(({ role, state, label, line }) => {
    const { shape } = CAST.find((c) => c.role === role);
    return `<li class="state-row">${liveMark({ shape, state, size, seed: `states-${role}` })}<span class="state-text"><span class="state-top">${displayName(shape, role)}<span class="state-label">${label}</span></span><span class="state-line">${line}</span></span></li>`;
  });
  return `<ul class="states-list marks-live">${rows.join('')}</ul>`;
}
