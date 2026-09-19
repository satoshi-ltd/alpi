import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../templates/theme.js', import.meta.url), 'utf8');
function page({ saved = null, dark = false, blocked = false } = {}) {
  const events = {};
  const root = { dataset: {} };
  const meta = { setAttribute: (_, value) => { meta.color = value; } };
  const button = { setAttribute: (_, value) => { button.label = value; } };
  const system = { matches: dark, addEventListener: (_, fn) => { system.change = fn; } };
  const storage = {
    getItem: () => { if (blocked) throw new Error('Storage unavailable'); return saved; },
    setItem: (_, value) => { if (blocked) throw new Error('Storage unavailable'); saved = value; },
  };
  runInNewContext(script, {
    document: {
      documentElement: root,
      querySelector: selector => selector === '.theme-btn' ? button : meta,
      addEventListener: (name, fn) => { events[name] = fn; },
    },
    matchMedia: () => system,
    localStorage: storage,
  });
  return { root, meta, button, system, saved: () => saved, click: () => events.click({ target: { closest: () => button } }) };
}

test('saved choice sets theme, browser color and accessible toggle before page content', () => {
  const p = page({ saved: 'light', dark: true });
  assert.equal(p.root.dataset.theme, 'light');
  assert.equal(p.meta.color, '#f6f3ec');
  assert.equal(p.button.label, 'Switch to dark theme');
  p.system.change();
  assert.equal(p.root.dataset.theme, 'light');
});

test('system preference follows changes until the user chooses', () => {
  const p = page({ saved: 'invalid' });
  assert.equal(p.root.dataset.theme, 'light');
  p.system.matches = true;
  p.system.change();
  assert.equal(p.root.dataset.theme, 'dark');
  p.click();
  assert.equal(p.saved(), 'light');
  assert.equal(p.meta.color, '#f6f3ec');
  p.system.change();
  assert.equal(p.root.dataset.theme, 'light');
  const nextPage = page({ saved: p.saved(), dark: true });
  assert.equal(nextPage.root.dataset.theme, 'light');
});

test('theme toggle works when browser storage is unavailable', () => {
  const p = page({ blocked: true });
  p.click();
  assert.equal(p.root.dataset.theme, 'dark');
  assert.equal(p.meta.color, '#0c0b09');
  assert.equal(p.button.label, 'Switch to light theme');
});
