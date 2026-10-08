import { test } from 'node:test';
import { foldTones } from '../../common/folds.mjs';
import assert from 'node:assert/strict';
import { contrastRatio, creaseTones, CREASE_MIN_CONTRAST } from '../../common/crease.mjs';
import { ACCENTS, ACCENT_FOLDS } from '../../common/accents.mjs';
import { readFileSync } from 'node:fs';
import { AGENTS_DIM, AGENTS_EASE, AGENTS_PASS_S, AGENTS_RIPPLE_S, AGENTS_STAGGER_S, AGENTS_STEP_S, CREAM, IDENTITIES, NIGHT, NIGHT_LOCKUP, PAPER, agentLadders, alpacaMark, brandCss, cardSvg, creaseLadders, favicon, identityStrip, lockup } from './brand.mjs';

const fills = svg => [...svg.matchAll(/<polygon [^>]*fill="(#[0-9a-f]{6})"/g)].map(m => m[1]);

test('the generated alpaca is twelve facets in one flat ink', () => {
  const svg = alpacaMark({ height: 34 });
  assert.equal(fills(svg).length, 12);
  assert.equal(new Set(fills(svg)).size, 1);
  assert.ok(fills(svg).includes(CREAM));
  assert.equal(fills(lockup()).length, 12);
  assert.equal(fills(favicon()).length, 9);
  assert.match(favicon(), /viewBox="0 0 100 100"/);
});

test('the identity strip holds the twelve objects, each named and in its colour', () => {
  const strip = identityStrip();
  const items = [...strip.matchAll(/<li>([\s\S]*?)<\/li>/g)].map(m => m[1]);
  assert.equal(items.length, 12);
  assert.equal(new Set(IDENTITIES.map(i => i.fold)).size, 12);
  assert.deepEqual(IDENTITIES.map(i => i.fold), IDENTITIES.map(i => ACCENT_FOLDS[i.colour]));
  IDENTITIES.forEach((identity, i) => {
    assert.ok(items[i].includes(`aria-label="${identity.name}"`));
    assert.ok(items[i].includes(`<title>${identity.name}</title>`));
    assert.ok(fills(items[i]).includes(identity.hex), identity.name);
  });
  assert.ok(strip.includes('aria-label="The twelve identities"'));
  assert.ok(items[0].includes('aria-label="amber diamond"'));
});

test('every crease ladder keeps three distinct tones at 3:1 on its ground', () => {
  const { night, light } = creaseLadders();
  for (const [ground, set] of [[NIGHT, night], [PAPER, light]]) {
    for (const [name, tones] of Object.entries(set)) {
      assert.equal(new Set(tones).size, 3, `${ground} ${name}`);
      for (const tone of tones) assert.ok(contrastRatio(tone, ground) >= CREASE_MIN_CONTRAST, `${ground} ${name} ${tone}`);
    }
  }
  assert.equal(night.lockup[0], '#ffffff');
});

test('the card is a self-contained SVG: the alpaca and the wordmark in the night lockup crease, nothing else', () => {
  const svg = cardSvg({ height: 630, fontData: 'QUJD' });
  assert.ok(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"'));
  assert.ok(svg.includes('data:font/woff2;base64,QUJD'));
  assert.ok(!svg.includes('<image'));
  assert.deepEqual([...svg.matchAll(/<text\b[^>]*>([^<]*)<\/text>/g)].map((m) => m[1]), ['alpi']);
  assert.ok(svg.includes('fill="url(#crease)"'));
  for (const tone of NIGHT_LOCKUP) assert.ok(svg.includes(`stop-color="${tone}"`), tone);
  assert.equal([...svg.matchAll(/aria-label="[a-z]+ [a-z]+"/g)].length, 0);
  assert.equal(cardSvg({ height: 630, fontData: 'QUJD' }), svg);
});

test('the lockup mark follows the app accent per theme and the favicon uses a mid amber', async () => {
  const { brandCss, lockup, favicon, INK, FAVICON_INK } = await import('./brand.mjs');
  const { foldTones } = await import('../../common/folds.mjs');
  const css = brandCss();
  foldTones(INK).forEach((fill, tone) => assert.ok(css.includes(`:root[data-theme="light"] .logo-mark .t${tone}{fill:${fill}}`)));
  assert.equal([...lockup().matchAll(/class="t[012]"/g)].length, 12);
  assert.ok(!identityStrip().includes('class="t'));
  assert.ok(!cardSvg({ height: 630, fontData: '' }).includes('class="t'));
  assert.ok(favicon().includes(foldTones(FAVICON_INK)[1]));
});

test('only the favicon uses the nine facet alpaca; the lockup and the cards keep the twelve', async () => {
  const { favicon, lockup, alpacaMark } = await import('./brand.mjs');
  assert.equal([...favicon().matchAll(/<polygon/g)].length, 9);
  assert.equal([...lockup({ height: 28 }).matchAll(/<polygon/g)].length, 12);
  assert.equal([...alpacaMark({ height: 200 }).matchAll(/<polygon/g)].length, 12);
});

test('the twelve accents each keep three distinct tones at 3:1 on both grounds', () => {
  const ladders = agentLadders();
  for (const [ground, set] of [[NIGHT, ladders.night], [PAPER, ladders.light]]) {
    assert.equal(set.length, 12);
    for (const [i, tones] of set.entries()) {
      assert.equal(new Set(tones).size, 3, `${ACCENTS[i][0]} on ${ground}`);
      for (const tone of tones) assert.ok(contrastRatio(tone, ground) >= CREASE_MIN_CONTRAST, `${ACCENTS[i][0]} ${tone} on ${ground}`);
    }
  }
});

test('the agents pass walks the accents in order, from amber back to amber, once in 30 seconds, as a ripple per band', () => {
  const css = brandCss();
  const ladders = agentLadders();
  const pct = (seconds) => Number(((seconds / AGENTS_PASS_S) * 100).toFixed(4));
  const dim = `${Math.round(AGENTS_DIM * 255).toString(16)}`;
  assert.equal(AGENTS_PASS_S, 30);
  for (const [ground, ladder] of [['night', ladders.night], ['paper', ladders.light]]) {
    for (const band of ['a', 'b', 'c']) {
      const prop = ground === 'night' ? `--agent-${band}` : `--agent-p${band}`;
      const body = css.match(new RegExp(`@keyframes agents-${band}-${ground}\\{((?:[^{}]*\\{[^}]*\\})*)\\}`))[1];
      const stops = [...body.matchAll(/([\d.]+)%\{--agent-p?[abc]:(#[0-9a-f]{6,8})\}/g)].map(m => [Number(m[1]), m[2]]);
      const index = 'abc'.indexOf(band);
      assert.equal(stops.length, 1 + 3 * 12, `${ground} ${band}`);
      assert.deepEqual(stops[0], [0, ladder[0][index]]);
      assert.deepEqual([...new Set([...body.matchAll(/(--agent-p?[abc]):/g)].map(m => m[1]))], [prop]);
      ladder.forEach((tones, i) => {
        const next = ladder[(i + 1) % 12][index];
        const start = i * AGENTS_STEP_S + AGENTS_STEP_S - AGENTS_RIPPLE_S;
        assert.deepEqual(stops.slice(1 + 3 * i, 4 + 3 * i), [
          [pct(start), tones[index]],
          [pct(start + AGENTS_RIPPLE_S / 2), `${next}${dim}`],
          [pct(start + AGENTS_RIPPLE_S), next],
        ], `${ground} ${band} step ${i}`);
      });
      assert.equal(stops.at(-1)[1], ladder[0][index]);
      assert.equal(stops.at(-1)[0], 100);
    }
  }
  assert.equal(ACCENTS[0][0], 'amber');
  assert.equal(ladders.night.length, ACCENTS.length);
  assert.deepEqual(ladders.night.map(tones => tones[0]), ACCENTS.map(([, hex]) => creaseTones(hex, NIGHT)[0]));
  assert.ok(AGENTS_STAGGER_S > 0 && 2 * AGENTS_STAGGER_S + AGENTS_RIPPLE_S < AGENTS_STEP_S);
});

test('the agents word rests on amber, animates once on both grounds at the same time (a theme change never restarts it) and only without reduced motion, and resets under forced colours and print', () => {
  const css = brandCss();
  const { night, light } = agentLadders();
  assert.ok(css.includes(`.hero h1 .crease-agents{--agent-a:${night[0][0]};--agent-b:${night[0][1]};--agent-c:${night[0][2]};--agent-pa:${light[0][0]};--agent-pb:${light[0][1]};--agent-pc:${light[0][2]};background-image:`));
  assert.match(css, /:root\[data-theme="light"\] \.hero h1 \.crease-agents\{background-image:[^}]*var\(--agent-pa\)[^}]*var\(--agent-pb\)[^}]*var\(--agent-pc\)/);
  assert.equal([...css.matchAll(/@property --agent-p?[abc]\{syntax:"<color>";inherits:false;/g)].length, 6);
  const gated = css.match(/@media \(prefers-reduced-motion:no-preference\)\{(.*?)\}\}/)[1];
  const bands = ground => ['a', 'b', 'c'].map((band, i) => `agents-${band}-${ground} 30s ${AGENTS_EASE} ${Number((i * AGENTS_STAGGER_S).toFixed(2))}s 1 both`);
  assert.ok(gated.includes(`animation:${[...bands('night'), ...bands('paper')].join(',')}}`));
  assert.ok(!gated.includes('animation-name'));
  assert.equal([...css.matchAll(/animation:agents-a-night/g)].length, 1);
  assert.ok(css.includes('@media (forced-colors:active){.hero h1 .crease-agents{background:none;color:CanvasText;animation:none}}'));
  assert.ok(css.includes('@media print{.hero h1 .crease-agents{background:none;color:#000;animation:none}}'));
});

test('the creases never move: the agents gradient keeps the fixed band stops of every other crease', () => {
  const css = brandCss();
  const gradient = css.match(/\.hero h1 \.crease-agents\{[^}]*background-image:([^}]*)\}/)[1];
  assert.ok(gradient.includes('calc(33% - ') && gradient.includes('calc(66% - '));
});

test('the colour change keeps the design system motion: one ease, a --dur-4 ripple, a --dur-1 stagger', () => {
  const tokens = readFileSync(new URL('../../desktop/src/styles/tokens.css', import.meta.url), 'utf8');
  const token = (name) => tokens.match(new RegExp(`--${name}:\\s*([^;]+);`))[1].replace(/\s/g, '');
  const seconds = (value) => Number(value.replace('ms', '')) / 1000;
  assert.equal(AGENTS_EASE, token('ease'));
  assert.equal(AGENTS_RIPPLE_S, seconds(token('dur-4')));
  assert.equal(AGENTS_STAGGER_S, seconds(token('dur-1')));
});
