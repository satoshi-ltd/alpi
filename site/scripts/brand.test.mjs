import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ACCENTS, ACCENT_SHAPES } from '../../common/accents.mjs';
import { BODY, LOOK, MOTION_CSS, SHAPE_ORDER, SHAPES, TURN } from '../../common/agentMarks.mjs';
import { contrastRatio, nameTone, NAME_MIN_CONTRAST } from '../../common/name.mjs';
import { shiftLightness } from '../../common/shapes.mjs';
import { markTone } from '../../common/markTone.mjs';
import { STATE_ROWS, castScript, familyRow, honeycomb, liveMark, statesHtml, twinBadge } from './brand.mjs';
import { AGENTS_FLOOR, AGENTS_PASS_S, AGENTS_TILE_EM, CARD_GROUND, CREAM, EYE_NIGHT, EYE_PAPER, FAVICON_CREAM, FAVICON_INK, IDENTITIES, INK, NIGHT, PAPER, CAST, CAST_TWIN, STATE_NAMES, agentTones, brandCss, heroTone, cardSvg, castCss, castHtml, castMark, demoProfiles, favicon, lockup, pairMark, profileName, twinMark } from './brand.mjs';

const paths = (svg) => [...svg.matchAll(/<path((?: class="[^"]+")?) d="([^"]+)"([^>]*)\/>/g)].map((m) => ({ d: m[2], attrs: m[1] + m[3] }));
const subpaths = (d) => d.match(/M/g).length;
const assetPath = (name) => readFileSync(new URL(`../assets/${name}`, import.meta.url), 'utf8').match(/ d="([^"]+)"/)[1];

test('the one-ink assets keep Twin as one evenodd path with the eyes cut out, no polygons and no alpaca', () => {
  for (const svg of [twinMark({ height: 34, cut: true }), favicon(), cardSvg({ height: 630 })]) {
    assert.ok(!svg.includes('<polygon'));
    const [mark, ...rest] = paths(svg);
    assert.equal(rest.length, 0);
    assert.match(mark.attrs, /fill-rule="evenodd"/);
    assert.equal(subpaths(mark.d), 3);
    assert.ok(!/alpaca/i.test(svg));
  }
});

test('Twin on the page is the head with two filled eyes over it in the theme eye ink', () => {
  assert.equal(EYE_PAPER, '#ffffff');
  assert.equal(EYE_NIGHT, '#000000');
  for (const svg of [twinMark({ height: 34 }), lockup()]) {
    const [body, eyes, ...rest] = paths(svg);
    assert.equal(rest.length, 0);
    assert.ok(body.attrs.includes('class="mark-body"') || svg.includes('class="mark-body"'));
    assert.equal(subpaths(body.d), 1);
    assert.ok(!body.attrs.includes('evenodd'));
    assert.equal(subpaths(eyes.d), 2);
    assert.ok(svg.includes('<path class="mark-eye"'));
    assert.ok(!/alpaca/i.test(svg));
  }
  const css = brandCss();
  assert.ok(css.includes(`.mark-eye{fill:var(--mark-eye,${EYE_NIGHT})}`));
  assert.ok(css.includes('.logo-mark .mark-body{fill:var(--brand-ink)}'));
});

test('the site mark draws exactly the path scripts/gen_icons.py writes into alpi-black.svg and alpi-white.svg', () => {
  const d = paths(twinMark({ fill: INK, cut: true }))[0].d;
  assert.equal(d, assetPath('alpi-black.svg'));
  assert.equal(d, assetPath('alpi-white.svg'));
  const viewBox = readFileSync(new URL('../assets/alpi-black.svg', import.meta.url), 'utf8').match(/viewBox="([^"]+)"/)[1];
  assert.ok(twinMark().includes(`viewBox="${viewBox}"`));
});

test('the favicon is Twin at half turn in one flat ink, centred in a square', () => {
  const svg = favicon();
  assert.match(svg, /viewBox="0 0 100 100"/);
  assert.deepEqual(paths(svg).map((p) => p.attrs.match(/fill="([^"]+)"/)[1]), [FAVICON_INK]);
  assert.equal(FAVICON_INK, INK);
  assert.match(svg, new RegExp(`@media \\(prefers-color-scheme: dark\\)\\{path\\{fill:${FAVICON_CREAM}\\}\\}`));
  assert.equal(FAVICON_CREAM, CREAM);
  const numbers = paths(svg)[0].d.match(/-?\d+\.\d+/g).map(Number);
  assert.ok(Math.min(...numbers) >= 0 && Math.max(...numbers) <= 100);
});

test('the lockup mark and wordmark follow the brand ink per theme, solid; only the agents word carries a gradient', () => {
  const css = brandCss();
  assert.ok(lockup().includes('<span class="logo-word display">alpi</span>'));
  assert.ok(!paths(lockup())[0].attrs.includes('fill="'));
  assert.ok(lockup().includes('class="mark-body"'));
  assert.ok(css.includes(`:root{--brand-ink:${CREAM}}`));
  assert.ok(css.includes(`:root[data-theme="light"]{--brand-ink:${INK}}`));
  assert.ok(css.includes('.logo-mark .mark-body{fill:var(--brand-ink)}'));
  assert.ok(css.includes('.display{font-weight:800;letter-spacing:-.04em;color:var(--brand-ink);display:inline-block}'));
  assert.ok(!/crease/i.test(css));
  const painted = css.split('\n').filter((line) => /gradient|background-clip/i.test(line));
  assert.ok(painted.length > 0 && painted.every((line) => line.includes('.hero h1 .display-agents')));
});

test('the card is a self-contained SVG: Twin in its held turn and the solid ink wordmark on white, nothing else', () => {
  const svg = cardSvg({ height: 630, fontData: 'QUJD' });
  assert.ok(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"'));
  assert.ok(svg.includes('data:font/woff2;base64,QUJD'));
  assert.ok(svg.includes('font-family:"Bricolage Grotesque";font-weight:800'));
  assert.ok(!svg.includes('<image') && !svg.includes('Gradient'));
  assert.ok(svg.includes(`<rect width="1200" height="630" fill="${CARD_GROUND}"/>`));
  assert.deepEqual([...svg.matchAll(/<text\b[^>]*>([^<]*)<\/text>/g)].map((m) => m[1]), ['alpi']);
  assert.match(svg, /<text [^>]*font-weight="800" letter-spacing="-8\.32" fill="#14110c">/);
  assert.match(paths(svg)[0].attrs, new RegExp(`fill="${INK}"`));
  assert.notEqual(paths(svg)[0].d, paths(twinMark({ cut: true }))[0].d);
  assert.equal(cardSvg({ height: 630, fontData: 'QUJD' }), svg);
});

test('each identity wears the shape paired with its accent, with two filled eyes over it', () => {
  assert.equal(IDENTITIES.length, 12);
  assert.equal(new Set(IDENTITIES.map((i) => i.shape)).size, 12);
  IDENTITIES.forEach(({ colour, hex, shape, name }) => {
    assert.equal(shape, ACCENT_SHAPES[colour]);
    assert.ok(SHAPE_ORDER.includes(shape));
    assert.equal(name, `${colour} ${shape}`);
    const svg = pairMark(shape, 24);
    const [mark, eyes] = paths(svg);
    assert.equal(mark.d, SHAPES[shape].d);
    assert.match(mark.attrs, new RegExp(`fill="${hex}"`));
    assert.equal(subpaths(eyes.d), 2);
    assert.match(eyes.attrs, /class="mark-eye"/);
    assert.ok(svg.includes(`<title>${name}</title>`));
  });
  assert.throws(() => pairMark('alpi-twin'));
  assert.throws(() => pairMark('shield'));
});

test('a profile name is its mark beside solid type in nameTone of its accent on each ground', () => {
  const html = profileName('bell', 'reviewer', 18);
  const { hex } = IDENTITIES.find((i) => i.shape === 'bell');
  assert.ok(html.includes(`style="--name-night:${nameTone(hex, NIGHT)};--name-paper:${nameTone(hex, PAPER)}">reviewer</span>`));
  for (const ground of [NIGHT, PAPER]) assert.ok(contrastRatio(nameTone(hex, ground), ground) >= NAME_MIN_CONTRAST);
  const css = brandCss();
  assert.ok(css.includes('.display-name{color:var(--name-night)}'));
  assert.ok(css.includes(':root[data-theme="light"] .display-name{color:var(--name-paper)}'));
  const demo = demoProfiles({ reviewer: 'bell' });
  assert.equal(demo.reviewer.color, hex);
  assert.match(demo.reviewer.mark, /^<svg viewBox="0 0 100 100" width="13"/);
});

const AGENT_GROUNDS = { night: NIGHT, paper: PAPER };
const channels = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const toHex = (rgb) => `#${rgb.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')}`;
const gradientStops = (css, ground, name) => {
  const block = ground === 'night' ? css.match(/\n\.hero h1 \.display-agents\{([^}]*)\}/)[1] : css.match(/:root\[data-theme="light"\] \.hero h1 \.display-agents\{([^}]*)\}/)[1];
  const gradient = block.match(new RegExp(`--agents-${name}:linear-gradient\\(90deg,([^)]*)\\)`))[1];
  return gradient.split(',').map((stop) => { const [tone, at] = stop.split(' '); return [tone, Number(at.replace('%', ''))]; });
};

test('the agents word flows through the twelve shipped accents, touched only where one falls under 3:1 on the page ground', () => {
  const tones = agentTones();
  for (const [ground, bg] of Object.entries(AGENT_GROUNDS)) {
    assert.equal(tones[ground].length, ACCENTS.length);
    ACCENTS.forEach(([, hex], i) => {
      const tone = tones[ground][i];
      assert.equal(tone, heroTone(hex, bg));
      assert.ok(contrastRatio(tone, bg) >= AGENTS_FLOOR, `${hex} on ${bg}`);
      if (contrastRatio(hex, bg) >= AGENTS_FLOOR) assert.equal(tone, hex);
    });
  }
  assert.deepEqual(tones.night, ACCENTS.map(([, hex]) => hex));
  assert.deepEqual(tones.paper, ACCENTS.map(([, hex]) => markTone(hex, 'light')));
  const touched = ACCENTS.filter(([, hex], i) => tones.paper[i] !== hex).map(([name]) => name);
  assert.deepEqual(touched, ['amber', 'orange', 'rose', 'sky', 'teal', 'green', 'lime']);
  for (const [name, hex] of ACCENTS.filter(([n]) => touched.includes(n))) {
    const tone = tones.paper[ACCENTS.findIndex(([n]) => n === name)];
    const steps = Array.from({ length: 100 }, (_, i) => Number(((i + 1) / 100).toFixed(2)));
    const step = steps.find((d) => shiftLightness(hex, -d) === tone);
    assert.ok(step, `${name} is a lightness step of its accent`);
    const before = step === 0.01 ? hex : shiftLightness(hex, -Number((step - 0.01).toFixed(2)));
    assert.ok(contrastRatio(before, PAPER) < AGENTS_FLOOR, `${name} moves no further than the floor needs`);
  }
});

test('every frame of the flow keeps 3:1 on its ground, sampled along the sRGB interpolation the browser paints', () => {
  const css = brandCss();
  for (const [ground, bg] of Object.entries(AGENT_GROUNDS)) {
    for (const name of ['flow', 'still']) {
      const stops = gradientStops(css, ground, name);
      assert.equal(stops[0][1], 0);
      assert.equal(stops.at(-1)[1], 100);
      for (let i = 0; i + 1 < stops.length; i++) {
        const [a, b] = [channels(stops[i][0]), channels(stops[i + 1][0])];
        for (let k = 0; k <= 64; k++) {
          const frame = toHex(a.map((v, j) => v + ((b[j] - v) * k) / 64));
          assert.ok(contrastRatio(frame, bg) >= AGENTS_FLOOR, `${ground} ${name} ${frame} ${contrastRatio(frame, bg).toFixed(2)}`);
        }
      }
    }
  }
});

test('the flow is one seamless tile of twelve bands that loops linearly, closing on the colour it opens with', () => {
  const css = brandCss();
  const tones = agentTones();
  for (const ground of Object.keys(AGENT_GROUNDS)) {
    const flow = gradientStops(css, ground, 'flow');
    assert.deepEqual(flow.map(([tone]) => tone), [...tones[ground], tones[ground][0]]);
    flow.forEach(([, at], i) => assert.equal(at, Number(((i / 12) * 100).toFixed(4))));
    assert.deepEqual(gradientStops(css, ground, 'still').map(([tone]) => tone), tones[ground]);
  }
  assert.equal(AGENTS_TILE_EM, 18);
  assert.ok(css.includes(`@keyframes agents-flow{from{background-position:0 0}to{background-position:-${AGENTS_TILE_EM}em 0}}`));
  assert.ok(css.includes(`background-size:${AGENTS_TILE_EM}em 100%;background-repeat:repeat-x;animation:agents-flow ${AGENTS_PASS_S}s linear infinite`));
});

test('reduced motion shows the still gradient, the flow runs only without it, pauses offscreen and never shifts the layout', () => {
  const css = brandCss();
  const base = css.match(/\n\.hero h1 \.display-agents\{([^}]*)\}/)[1];
  assert.ok(base.includes('padding:.12em .06em;margin:-.12em -.06em'));
  assert.ok(!base.includes('animation'));
  assert.ok(css.includes('@supports (-webkit-background-clip:text) or (background-clip:text){.hero h1 .display-agents{background:var(--agents-still);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent}}'));
  const gated = css.match(/@media \(prefers-reduced-motion:no-preference\)\{(.*)\}\n/)[1];
  assert.ok(gated.includes('animation:agents-flow'));
  assert.ok(gated.includes('.hero.is-away h1 .display-agents{animation-play-state:paused}'));
  assert.equal([...css.matchAll(/animation:agents-flow/g)].length, 1);
  assert.ok(!/@property --agent/.test(css));
  assert.ok(!/\b(width|height|font-size|letter-spacing)\s*:/.test(gated));
  assert.match(css, /@media \(forced-colors:active\)\{[^}]*\.hero h1 \.display-agents\{color:CanvasText;-webkit-text-fill-color:CanvasText;background:none;animation:none\}/);
  assert.match(css, /@media print\{[^}]*\.hero h1 \.display-agents\{color:#000;-webkit-text-fill-color:#000;background:none;animation:none\}/);
});

test('the cast is the twelve shapes in SHAPE_ORDER, each in its own accent, and Twin in the brand ink', () => {
  assert.deepEqual(CAST.map((c) => c.shape), SHAPE_ORDER);
  const html = castHtml();
  const bodies = [...html.matchAll(/data-shape="([\w-]+)" data-state="(\w+)"[^>]*>[\s\S]*?<path class="mark-(body|rest)(?: mark-toned)?" d="([^"]+)"(?: fill="([^"]+)")?(?: style="--mark-paper:(#[0-9a-f]{6})")?/g)];
  assert.equal(bodies.length, 13);
  const byShape = Object.fromEntries(bodies.map((m) => [m[1], { state: m[2], kind: m[3], d: m[4], fill: m[5], paper: m[6] }]));
  for (const { shape, state } of CAST) {
    assert.equal(byShape[shape].state, state, shape);
    assert.equal(byShape[shape].d, SHAPES[shape].d, shape);
    if (state === 'paused') continue;
    const hex = ACCENTS.find(([colour]) => ACCENT_SHAPES[colour] === shape)[1];
    assert.equal(byShape[shape].fill, hex, shape);
    assert.equal(byShape[shape].paper ?? hex, markTone(hex, 'light'), shape);
  }
  assert.equal(byShape['alpi-twin'].fill, 'var(--brand-ink)');
  assert.equal(byShape['alpi-twin'].state, CAST_TWIN.state);
  assert.ok(!/alpaca/i.test(html));
});

test('the cast states are a fixed believable mix: mostly at work, one failure, one paused', () => {
  const count = (state) => CAST.filter((c) => c.state === state).length;
  assert.equal(count('failed'), 1);
  assert.equal(count('paused'), 1);
  assert.ok(count('working') >= 2 && count('needs') >= 1 && count('done') >= 1 && count('idle') >= 1);
  assert.equal(castHtml(), castHtml());
  assert.equal(new Set(CAST.map((c) => c.role)).size, CAST.length);
});

test('the cast is one tab stop: every member is named by role and state, with a tooltip in its name tone, and only the first takes Tab', () => {
  const html = castHtml();
  assert.deepEqual([...html.matchAll(/tabindex="(-?\d)"/g)].map((m) => m[1]), ['0', ...Array(12).fill('-1')]);
  const items = [...html.matchAll(/<span class="cast-item[^"]*" tabindex="-?\d" role="img" aria-label="([^"]+)"[^>]*>[\s\S]*?<span class="cast-tip" aria-hidden="true"><span class="display-name" style="--name-night:([^;]+);--name-paper:([^"]+)">(\w+)<\/span> · ([\w ]+)<\/span><\/span>/g)];
  assert.equal(items.length, 13);
  const expected = [...CAST.slice(0, 6), CAST_TWIN, ...CAST.slice(6)].map(({ role, state }) => `${role} · ${STATE_NAMES[state]}`);
  assert.deepEqual(items.map((m) => m[1]), expected);
  assert.ok(items.some((m) => m[1] === 'scout · working') && items.some((m) => m[1] === 'lens · needs you'));
  for (const [, label, night, paper, name, state] of items) assert.equal(label, `${name} · ${state}`);
  for (const { shape, role } of CAST) {
    const hex = ACCENTS.find(([colour]) => ACCENT_SHAPES[colour] === shape)[1];
    const item = items.find((m) => m[4] === role);
    assert.equal(item[2], nameTone(hex, NIGHT), role);
    assert.equal(item[3], nameTone(hex, PAPER), role);
  }
  assert.match(html, /^<div class="cast" role="group" aria-label="[^"]+">/);
  for (const svg of html.match(/<svg[^>]*>/g)) assert.ok(svg.includes('aria-hidden="true"'), svg);
});

test('a live cast mark runs the apps motion in CSS only: turn, eye parallax, lids and body per state', () => {
  for (const state of ['idle', 'busy', 'working', 'needs', 'done', 'failed']) {
    const svg = castMark({ shape: 'round', fill: '#000000', state });
    assert.ok(svg.includes(`class="vt-a vt-turn-${state}"`), state);
    assert.ok(svg.includes(`class="vt-a vt-eyes-${state}"`), state);
    assert.ok(svg.includes(`class="am-a am-lid-${LOOK[state]}"`), state);
    assert.ok(svg.includes(`class="am-a am-body-${BODY[state]}"`), state);
    const [ry, rx, rz] = TURN.still[state];
    assert.ok(svg.includes(`transform:rotateY(${ry}deg) rotateX(${rx}deg) rotateZ(${rz}deg)`), state);
    assert.ok(svg.includes('class="mark-eye"') && !/<animate|<script/.test(svg), state);
  }
});

test('a paused cast mark is a dashed neutral outline with sleepy eyes and no motion', () => {
  const svg = castMark({ shape: 'cloud', fill: '#000000', state: 'paused' });
  assert.match(svg, /<path class="mark-rest" d="[^"]+" fill="none" stroke-width="3\.6" stroke-dasharray="6\.5 5" stroke-linecap="round"\/>/);
  assert.ok(svg.includes('class="mark-rest-eye"'));
  assert.ok(!/am-a|vt-a|#000000/.test(svg));
});

test('the cast motion pauses off screen, stops under reduced motion and drops the pointer turn', () => {
  const css = castCss();
  assert.ok(css.startsWith(MOTION_CSS));
  assert.ok(css.includes('.is-away .am-a,.is-away .vt-a{animation-play-state:paused}'));
  assert.ok(css.includes('@media (prefers-reduced-motion:reduce){.am-a,.vt-a{animation:none}}'));
  assert.ok(!/:hover/.test(css));
  assert.ok(!/class="[^"]*\bvt-(turn|eyes)\b(?!-)/.test(castHtml()));
});


function fakeCast(count) {
  const items = Array.from({ length: count }, (_, i) => ({ tabIndex: i ? -1 : 0, focus() { doc.activeElement = this; } }));
  const listeners = {};
  const cast = { querySelectorAll: () => items, addEventListener: (type, fn) => { listeners[type] = fn; } };
  const doc = { activeElement: items[0], querySelector: () => cast };
  const press = (key) => { let prevented = false; listeners.keydown({ key, preventDefault: () => { prevented = true; } }); return prevented; };
  return { items, doc, press };
}

test('the arrow keys rove the one tab stop through the cast and wrap at the ends; other keys pass through', () => {
  const { items, doc, press } = fakeCast(13);
  globalThis.document = doc;
  try {
    new Function(castScript())();
    assert.ok(press('ArrowRight'));
    assert.equal(doc.activeElement, items[1]);
    assert.deepEqual(items.map((i) => i.tabIndex).filter((t) => t === 0).length, 1);
    assert.equal(items[1].tabIndex, 0);
    press('ArrowLeft'); press('ArrowLeft');
    assert.equal(doc.activeElement, items[12]);
    press('Home');
    assert.equal(doc.activeElement, items[0]);
    press('End');
    assert.equal(doc.activeElement, items[12]);
    assert.equal(press('Tab'), false);
    assert.equal(items.filter((i) => i.tabIndex === 0).length, 1);
  } finally {
    delete globalThis.document;
  }
});

test('a profile name beside its mark hides the mark from assistive tech, so the name is read once', () => {
  for (const html of [profileName('bell', 'reviewer', 20), profileName('bell', 'reviewer', 40, 'working')]) {
    assert.ok(!/aria-label=/.test(html), html);
    assert.ok(!/<title>/.test(html));
    assert.match(html, /aria-hidden="true"/);
    assert.ok(html.includes('>reviewer</span>'));
  }
});

test('a live mark draws the apps motion from 20 px, holds still below it and turns less at row size', () => {
  assert.match(liveMark({ shape: 'bell', state: 'working', size: 32 }), /class="vt-a vt-turn-working"/);
  assert.match(liveMark({ shape: 'bell', state: 'done', size: 20 }), /class="vt-a vt-turn-done"/);
  const small = liveMark({ shape: 'bell', state: 'working', size: 16 });
  assert.ok(!/vt-a|am-a/.test(small));
  const turn = (html) => html.match(/transform:rotateY\((-?[\d.]+)deg\)/)[1];
  assert.equal(Number(turn(liveMark({ shape: 'bell', state: 'done', size: 20 }))), TURN.still.done[0] * TURN.smallTurn);
  assert.equal(Number(turn(liveMark({ shape: 'bell', state: 'done', size: 40 }))), TURN.still.done[0]);
  assert.match(liveMark({ shape: 'bell', state: 'idle', size: 40 }), /^<span class="live-mark" style="--size:40px" aria-hidden="true">/);
});

test('the footer family is the twelve shapes still, in accent order, hidden from assistive tech', () => {
  const row = familyRow(20);
  assert.match(row, /^<span class="family" aria-hidden="true">/);
  const shapes = [...row.matchAll(/data-shape="([\w-]+)"/g)].map((m) => m[1]);
  assert.deepEqual(shapes, IDENTITIES.map((i) => i.shape));
  assert.equal(shapes.length, 12);
  assert.ok(!/vt-a|am-a|<animate|aria-label/.test(row));
  for (const { hex } of IDENTITIES) assert.ok(row.includes(`fill="${hex}"`), hex);
});

test('the states list names the five states the cast plays, with the cast pairs, marks hidden beside text', () => {
  assert.deepEqual(STATE_ROWS.map((r) => r.state), ['working', 'needs', 'done', 'failed', 'paused']);
  const html = statesHtml();
  const rows = [...html.matchAll(/<li class="state-row"><span class="live-mark" style="--size:52px" aria-hidden="true"><svg[^>]*data-shape="([\w-]+)" data-state="(\w+)"[\s\S]*?<span class="display display-name"[^>]*>(\w+)<\/span><span class="state-label">([^<]+)<\/span>/g)];
  assert.equal(rows.length, 5);
  for (const [, shape, state, role, label] of rows) {
    assert.equal(CAST.find((c) => c.role === role).shape, shape, role);
    assert.ok(label.startsWith(STATE_NAMES[state]), label);
  }
  assert.deepEqual(rows.map((r) => r[2]), ['working', 'needs', 'done', 'failed', 'paused']);
});

test('the workgroup rung draws the soft honeycomb with the top cell lit in the owner accent, still and hidden', () => {
  const html = honeycomb('bell', 44);
  const hex = IDENTITIES.find((i) => i.shape === 'bell').hex;
  assert.match(html, /aria-hidden="true"/);
  assert.match(html, /data-mark="soft-honeycomb"/);
  assert.match(html, new RegExp(`data-cell="top" data-lead="" d="[^"]+" fill="${hex}"`));
  assert.equal([...html.matchAll(/data-cell=/g)].length, 3);
  assert.ok(!/vt-a|am-a/.test(html));
});

test('the post badge is Twin in its held turn in the brand ink, hidden from assistive tech', () => {
  const svg = twinBadge(40);
  assert.match(svg, /class="twin-mark"/);
  assert.match(svg, /aria-hidden="true"/);
  assert.ok(brandCss().includes('.twin-mark .mark-body{fill:var(--brand-ink)}'));
});

test('a pale accent wears its mark tone on paper so the white eyes hold 3:1, and its stored accent on night', () => {
  assert.ok(brandCss().includes(':root[data-theme="light"] .mark-toned{fill:var(--mark-paper)}'));
  for (const { shape, hex } of IDENTITIES) {
    const svg = pairMark(shape, 24, false);
    const paper = markTone(hex, 'light');
    assert.ok(svg.includes(`fill="${hex}"`), shape);
    assert.ok(contrastRatio(paper, EYE_PAPER) >= 3, shape);
    if (paper === hex) assert.ok(!svg.includes('mark-toned'), shape);
    else assert.ok(svg.includes(`class="mark-body mark-toned" d="${SHAPES[shape].d}" fill="${hex}" style="--mark-paper:${paper}"`), shape);
  }
  assert.ok(pairMark('round').includes('--mark-paper:#c08915'));
});

test('printing deepens a pale mark body under its white eyes, whatever the screen theme', async () => {
  const { brandCss } = await import('./brand.mjs');
  assert.match(brandCss(), /@media print\{[^\n]*\.mark-toned\{fill:var\(--mark-paper\)\}\.mark-eye\{fill:#fff\}\}/);
});
