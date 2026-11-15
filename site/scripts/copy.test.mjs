import { test } from 'node:test';
import assert from 'node:assert/strict';
import { COPIED, COPY_FAILED, COPY_HOLD_MS, copyButton, copyCss, copyScript } from './copy.mjs';

const button = copyButton({ text: 'a "b" <c>', shown: 'shown', label: 'Copy it', className: 'pill' });

test('a copy button carries the copy and check icons and both labels inside itself', () => {
  assert.match(button, /^<button class="copy pill" type="button" data-copy="a &quot;b&quot; &lt;c&gt;" aria-label="Copy it">/);
  assert.match(button, /<span class="copy-swap copy-icon" aria-hidden="true"><svg class="copy-glyph copy-idle"[\s\S]*?<\/svg><svg class="copy-glyph copy-done"[\s\S]*?<\/svg><\/span>/);
  assert.ok(button.endsWith(`<span class="copy-swap copy-text" aria-hidden="true"><span class="copy-idle">shown</span><span class="copy-done">${COPIED}</span></span></button>`));
});

test('the swap stacks both states in one cell, so the width never jumps', () => {
  const css = copyCss();
  assert.ok(css.includes('.copy-swap{display:inline-grid;justify-items:center;align-items:center}'));
  assert.ok(css.includes('.copy-swap>*{grid-area:1/1}'));
  assert.ok(css.includes('.copy .copy-done,.copy.is-copied .copy-idle{visibility:hidden}'));
  assert.ok(css.includes('.copy.is-copied .copy-done{visibility:visible}'));
  assert.ok(!/display:none/.test(css));
});

function fakeDom() {
  const listeners = {};
  const appended = [];
  const classes = new Set();
  const target = {
    dataset: { copy: 'uv tool install alpi-agent' },
    classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c) },
  };
  target.closest = () => target;
  const document = {
    addEventListener: (type, fn) => { listeners[type] = fn; },
    createElement: () => ({ attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, textContent: '' }),
    body: { appendChild: (el) => appended.push(el) },
  };
  return { listeners, appended, classes, target, document };
}

test('a click copies, marks the button copied, announces once in a live region off the button and resets', async () => {
  const dom = fakeDom();
  const written = [];
  const timers = [];
  const run = new Function('document', 'navigator', 'setTimeout', 'clearTimeout', copyScript());
  run(dom.document, { clipboard: { writeText: async (t) => { written.push(t); } } }, (fn, ms) => timers.push([fn, ms]), () => {});
  assert.equal(dom.appended.length, 1);
  assert.equal(dom.appended[0].textContent, '');
  dom.listeners.click({ target: dom.target });
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(written, ['uv tool install alpi-agent']);
  assert.ok(dom.classes.has('is-copied'));
  assert.equal(dom.appended.length, 1);
  const [status] = dom.appended;
  assert.equal(status.className, 'sr-only');
  assert.equal(status.attrs['aria-live'], 'polite');
  assert.equal(status.textContent, COPIED);
  assert.equal(timers[0][1], COPY_HOLD_MS);
  timers[0][0]();
  assert.ok(!dom.classes.has('is-copied'));
  assert.equal(status.textContent, '');
});

test('a refused clipboard announces the failure and never shows the check', async () => {
  const dom = fakeDom();
  const run = new Function('document', 'navigator', 'setTimeout', 'clearTimeout', copyScript());
  run(dom.document, { clipboard: { writeText: async () => { throw new Error('denied'); } } }, () => {}, () => {});
  dom.listeners.click({ target: dom.target });
  await new Promise((r) => setImmediate(r));
  assert.ok(!dom.classes.has('is-copied'));
  assert.equal(dom.appended[0].textContent, COPY_FAILED);
});

test('a second copy inside the hold is announced again, not swallowed as the same text', async () => {
  const dom = fakeDom();
  const run = new Function('document', 'navigator', 'setTimeout', 'clearTimeout', copyScript());
  run(dom.document, { clipboard: { writeText: async () => {} } }, () => {}, () => {});
  dom.listeners.click({ target: dom.target });
  await new Promise((r) => setImmediate(r));
  const first = dom.appended[0].textContent;
  dom.listeners.click({ target: dom.target });
  await new Promise((r) => setImmediate(r));
  assert.notEqual(dom.appended[0].textContent, first);
  assert.equal(dom.appended[0].textContent.replace('\u200b', ''), COPIED);
});
