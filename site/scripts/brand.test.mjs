import { test } from 'node:test';
import { foldTones } from '../../common/folds.mjs';
import assert from 'node:assert/strict';
import { contrastRatio, CREASE_MIN_CONTRAST } from '../../common/crease.mjs';
import { ACCENT_FOLDS } from '../../common/accents.mjs';
import { CREAM, IDENTITIES, NIGHT, PAPER, alpacaMark, cardSvg, creaseLadders, favicon, identityStrip, lockup } from './brand.mjs';

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

test('the card is a self-contained SVG with the crease wordmark and the twelve identities', () => {
  const svg = cardSvg({ height: 630, fontData: 'QUJD' });
  assert.ok(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"'));
  assert.ok(svg.includes('data:font/woff2;base64,QUJD'));
  assert.ok(!svg.includes('<image'));
  assert.ok(svg.includes('>alpi</text>'));
  assert.ok(svg.includes('fill="url(#crease)"'));
  assert.equal([...svg.matchAll(/aria-label="[a-z]+ [a-z]+"/g)].length, 12);
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
