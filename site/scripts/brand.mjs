import { ACCENTS, ACCENT_FOLDS } from '../../common/accents.mjs';
import { CREASE_ANGLE, CREASE_FONT, contrastRatio, creaseGradient, creaseTones } from '../../common/crease.mjs';
import { ALPACA_LOW_FOLD, BRAND_INK, foldPolygons, foldTones } from '../../common/folds.mjs';
import { palettes } from '../../common/tokens.mjs';

export const NIGHT = palettes.dark.bg;
export const PAPER = palettes.light.bg;
export const CREAM = BRAND_INK.dark;
export const INK = BRAND_INK.light;
export const FAVICON_INK = '#7a7468';
export const NIGHT_LOCKUP = [CREAM, '#ffffff', '#b9b3a4'];
export const FONT_FILE = 'bricolage-800-latin.woff2';
export const FONT_URL = `assets/fonts/${FONT_FILE}`;
export const LOCKUP_SLIT = 0.6;
export const HERO_SLIT = 0.7;
export const TAGLINE = 'Your private agent network.';
export const AGENTS_STEP_S = 2.5;
export const AGENTS_RIPPLE_S = 0.36;
export const AGENTS_STAGGER_S = 0.12;
export const AGENTS_EASE = 'cubic-bezier(.2,.7,.2,1)';
export const AGENTS_DIM = 0.5;
export const AGENTS_PASS_S = AGENTS_STEP_S * ACCENTS.length;

export const IDENTITIES = ACCENTS.map(([colour, hex]) => ({
  colour,
  hex,
  fold: ACCENT_FOLDS[colour],
  name: `${colour} ${ACCENT_FOLDS[colour]}`,
}));

const fixed = (n) => Number(n.toFixed(2));
const polygonTag = ({ points, fill, tone }, themed = false) => `<polygon${themed ? ` class="t${tone}"` : ''} points="${points.map(([x, y]) => `${fixed(x)},${fixed(y)}`).join(' ')}" fill="${fill}"/>`;
const bounds = (polygons) => {
  const xs = polygons.flatMap((p) => p.points.map((q) => q[0]));
  const ys = polygons.flatMap((p) => p.points.map((q) => q[1]));
  return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
};
const a11y = (label) => (label ? `role="img" aria-label="${label}"` : 'aria-hidden="true" focusable="false"');

export function alpacaMark({ accent = CREAM, height = 64, className = '', label = '', square = false, themed = false, small = false } = {}) {
  const polygons = foldPolygons(small ? ALPACA_LOW_FOLD : 'alpaca', accent, height);
  const box = bounds(polygons);
  const viewBox = square ? '0 0 100 100' : `${fixed(box.x)} ${fixed(box.y)} ${fixed(box.w)} ${fixed(box.h)}`;
  const width = square ? height : fixed((height * box.w) / box.h);
  const cls = className ? ` class="${className}"` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg"${cls} viewBox="${viewBox}" width="${width}" height="${height}" ${a11y(label)}>${polygons.map((p) => polygonTag(p, themed)).join('')}</svg>`;
}

export function favicon() {
  return alpacaMark({ accent: FAVICON_INK, height: 64, label: 'alpi', square: true, small: true });
}

export function identityMark({ fold, hex, name, size = 34 }) {
  const polygons = foldPolygons(fold, hex, size).map((p) => polygonTag(p)).join('');
  return `<svg viewBox="0 0 100 100" width="${size}" height="${size}" role="img" aria-label="${name}"><title>${name}</title>${polygons}</svg>`;
}

const identityFor = (fold) => {
  const identity = IDENTITIES.find((item) => item.fold === fold);
  if (!identity) throw new Error(`no identity wears the fold "${fold}"`);
  return identity;
};

export function pairMark(fold, size = 24) {
  return identityMark({ ...identityFor(fold), size });
}

export function profileName(fold, name, size = 18) {
  const { hex } = identityFor(fold);
  const night = creaseGradient(creaseTones(hex, NIGHT));
  const paper = creaseGradient(creaseTones(hex, PAPER));
  return `<span class="profile-name">${pairMark(fold, size)}<span class="crease crease-name" style="--crease-night:${night};--crease-paper:${paper}">${name}</span></span>`;
}

export function demoProfiles(byName, size = 13) {
  return Object.fromEntries(Object.entries(byName).map(([name, fold]) => {
    const identity = identityFor(fold);
    return [name, { color: identity.hex, mark: identityMark({ ...identity, size }) }];
  }));
}

export function identityStrip({ size = 34 } = {}) {
  const items = IDENTITIES.map((identity) => `<li>${identityMark({ ...identity, size })}</li>`).join('');
  return `<ul class="identities" aria-label="The twelve identities">${items}</ul>`;
}

export function lockup({ height = 34 } = {}) {
  return `<span class="logo">${alpacaMark({ height, className: 'logo-mark', themed: true, })}<span class="logo-word crease">alpi</span></span>`;
}

const ladders = (ground, ink) => ({
  lockup: creaseTones(ink, ground),
  first: creaseTones(ink, ground),
  second: creaseTones(ink === CREAM ? '#ffffff' : ink, ground),
});

export function creaseLadders() {
  return { night: ladders(NIGHT, CREAM), light: ladders(PAPER, INK) };
}

const tokens = (set) => [
  `--crease-lockup:${creaseGradient(set.lockup, LOCKUP_SLIT)}`,
  `--crease-first:${creaseGradient(set.first, HERO_SLIT)}`,
  `--crease-second:${creaseGradient(set.second, HERO_SLIT)}`,
].join(';');

const agentHexes = () => ACCENTS.map(([, hex]) => hex);

export function agentLadders() {
  return { night: agentHexes().map((hex) => creaseTones(hex, NIGHT)), light: agentHexes().map((hex) => creaseTones(hex, PAPER)) };
}

const AGENT_BANDS = ['a', 'b', 'c'];
const AGENT_PROPS = { night: AGENT_BANDS.map((band) => `--agent-${band}`), paper: AGENT_BANDS.map((band) => `--agent-p${band}`) };
const agentPct = (seconds) => Number(((seconds / AGENTS_PASS_S) * 100).toFixed(4));
const dimmed = (tone) => `${tone}${Math.round(AGENTS_DIM * 255).toString(16).padStart(2, '0')}`;

function agentKeyframes(name, prop, ladder, band) {
  const hold = AGENTS_STEP_S - AGENTS_RIPPLE_S;
  const stops = [`0%{${prop}:${ladder[0][band]}}`];
  ladder.forEach((tones, i) => {
    const next = ladder[(i + 1) % ladder.length][band];
    const start = i * AGENTS_STEP_S + hold;
    stops.push(
      `${agentPct(start)}%{${prop}:${tones[band]}}`,
      `${agentPct(start + AGENTS_RIPPLE_S / 2)}%{${prop}:${dimmed(next)}}`,
      `${agentPct(start + AGENTS_RIPPLE_S)}%{${prop}:${next}}`,
    );
  });
  return `@keyframes ${name}{${stops.join('')}}`;
}

const agentRest = (ground, tones) => tones.map((tone, i) => `${AGENT_PROPS[ground][i]}:${tone}`).join(';');
const agentGradient = (ground) => creaseGradient(AGENT_PROPS[ground].map((prop) => `var(${prop})`), HERO_SLIT);
const agentAnimation = () => ['night', 'paper'].flatMap((ground) => AGENT_BANDS.map((band, i) => `agents-${band}-${ground} ${AGENTS_PASS_S}s ${AGENTS_EASE} ${Number((i * AGENTS_STAGGER_S).toFixed(2))}s 1 both`)).join(',');

function agentsCss() {
  const { night, light } = agentLadders();
  const ladders = { night, paper: light };
  return [
    ...['night', 'paper'].flatMap((ground) => AGENT_PROPS[ground].map((prop) => `@property ${prop}{syntax:"<color>";inherits:false;initial-value:${ladders[ground][0][0]}}`)),
    ...['night', 'paper'].flatMap((ground) => AGENT_BANDS.map((band, i) => agentKeyframes(`agents-${band}-${ground}`, AGENT_PROPS[ground][i], ladders[ground], i))),
    `.hero h1 .crease-agents{${agentRest('night', night[0])};${agentRest('paper', light[0])};background-image:${agentGradient('night')}}`,
    `:root[data-theme="light"] .hero h1 .crease-agents{background-image:${agentGradient('paper')}}`,
    `@media (prefers-reduced-motion:no-preference){.hero h1 .crease-agents{animation:${agentAnimation()}}.hero.is-away h1 .crease-agents{animation-play-state:paused}}`,
  ];
}

export function brandCss() {
  const { night, light } = creaseLadders();
  return [
    `@font-face{font-family:"${CREASE_FONT}";font-style:normal;font-weight:800;font-display:swap;src:url("${FONT_URL}") format("woff2")}`,
    `:root{${tokens(night)}}`,
    `:root[data-theme="light"]{${tokens(light)}}`,
    ...foldTones(INK).map((fill, tone) => `:root[data-theme="light"] .logo-mark .t${tone}{fill:${fill}}`),
    `.logo .logo-word.crease,.hero h1 .crease,h1.crease-heading,h2.crease-heading,.crease-name{font-family:"${CREASE_FONT}","Instrument Sans",system-ui,sans-serif}`,
    `.crease{font-weight:800;letter-spacing:-.04em;-webkit-background-clip:text;background-clip:text;color:transparent;display:inline-block;padding:.06em 0 .22em;margin:-.06em 0 -.22em}`,
    `:root .logo .logo-word.crease{background-image:var(--crease-lockup);color:transparent;font-weight:800;letter-spacing:-.04em}`,
    `.hero h1 .crease{display:block;width:fit-content}`,
    `.profile-name{display:inline-flex;align-items:center;gap:.45em;vertical-align:middle}`,
    `.profile-name svg{flex:none;display:block}`,
    `.crease-name{letter-spacing:-.03em;background-image:var(--crease-night)}`,
    `:root[data-theme="light"] .crease-name{background-image:var(--crease-paper)}`,
    `.hero h1 .crease-first{background-image:var(--crease-first)}`,
    `.hero h1 .crease-second{background-image:var(--crease-second)}`,
    ...agentsCss(),
    `.hero h1 .hero-line{display:flex;column-gap:.24em}`,
    `h1.crease-heading{display:block;width:fit-content;max-width:100%;padding:0 0 .12em;font-weight:800;letter-spacing:-.03em;line-height:1.08;background-image:var(--crease-second)}`,
    `h2.crease-heading{display:block;width:fit-content;margin:15px 0 25px;padding:0 0 .12em;font-weight:800;letter-spacing:-.03em;line-height:1.1;background-image:var(--crease-second)}`,
    `@media (forced-colors:active){.crease,:root .logo .logo-word.crease,h1.crease-heading,h2.crease-heading{background:none;color:CanvasText}}`,
    `@media print{.crease,:root .logo .logo-word.crease,h1.crease-heading,h2.crease-heading{background:none;color:#000}}`,
    `@media (forced-colors:active){.hero h1 .crease-agents{background:none;color:CanvasText;animation:none}}`,
    `@media print{.hero h1 .crease-agents{background:none;color:#000;animation:none}}`,
    '',
  ].join('\n');
}

const stop = (offset, color, opacity = 1) => `<stop offset="${Number(offset.toFixed(4))}" stop-color="${color}"${opacity < 1 ? ` stop-opacity="${opacity}"` : ''}/>`;

function svgGradient(id, tones, box, slit) {
  const angle = (CREASE_ANGLE * Math.PI) / 180;
  const [dx, dy] = [Math.sin(angle), -Math.cos(angle)];
  const length = Math.abs(box.w * dx) + Math.abs(box.h * dy);
  const [cx, cy] = [box.x + box.w / 2, box.y + box.h / 2];
  const g = slit / length;
  const [a, b, c] = tones;
  const stops = [
    stop(0, a), stop(0.33 - g, a), stop(0.33 - g, a, 0), stop(0.33 + g, b, 0), stop(0.33 + g, b),
    stop(0.66 - g, b), stop(0.66 - g, b, 0), stop(0.66 + g, c, 0), stop(0.66 + g, c), stop(1, c),
  ].join('');
  const [x1, y1, x2, y2] = [cx - (dx * length) / 2, cy - (dy * length) / 2, cx + (dx * length) / 2, cy + (dy * length) / 2].map(fixed);
  return `<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}">${stops}</linearGradient>`;
}

const WORD_WIDTH = 1.45;

export function cardSvg({ width = 1200, height = 630, fontData = '' } = {}) {
  const markHeight = Math.round(height * 0.5);
  const mark = alpacaMark({ height: markHeight });
  const markWidth = Number(mark.match(/ width="([\d.]+)"/)[1]);
  const fontSize = Math.round(markHeight * 0.66);
  const wordWidth = fontSize * WORD_WIDTH;
  const gap = Math.round(markHeight * 0.3);
  const top = Math.round((height - markHeight) / 2);
  const left = Math.round((width - (markWidth + gap + wordWidth)) / 2);
  const baseline = top + Math.round(markHeight * 0.9);
  const box = { x: left + markWidth + gap, y: baseline - fontSize * 0.75, w: wordWidth, h: fontSize * 0.98 };
  const tones = NIGHT_LOCKUP;
  const font = fontData
    ? `<style>@font-face{font-family:"${CREASE_FONT}";font-weight:800;src:url(data:font/woff2;base64,${fontData}) format("woff2")}</style>`
    : '';
  const inner = mark.replace(/^<svg [^>]*?viewBox="([^"]+)"[^>]*>/, (_, vb) => `<svg x="${left}" y="${top}" width="${markWidth}" height="${markHeight}" viewBox="${vb}" aria-hidden="true">`);
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="alpi — ${TAGLINE.toLowerCase().replace(/\.$/, '')}">`,
    font,
    `<defs>${svgGradient('crease', tones, box, Math.max(0.6, fontSize / 140))}</defs>`,
    `<rect width="${width}" height="${height}" fill="${NIGHT}"/>`,
    inner,
    `<text x="${box.x}" y="${baseline}" font-family="${CREASE_FONT}, Instrument Sans, Arial Black, sans-serif" font-size="${fontSize}" font-weight="800" letter-spacing="${-0.04 * fontSize}" fill="url(#crease)">alpi</text>`,
    '</svg>',
    '',
  ].join('');
}
