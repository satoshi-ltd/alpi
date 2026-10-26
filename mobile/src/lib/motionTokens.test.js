import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { motion } from '../theme/tokens';

const ROOT = join(import.meta.dirname, '..', '..');

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (/\.jsx?$/.test(name) && !/\.test\./.test(name)) out.push(path);
  }
  return out;
}

const sources = [...walk(join(ROOT, 'src')), ...walk(join(ROOT, 'app'))].map((path) => [path.slice(ROOT.length + 1), readFileSync(path, 'utf8')]);

describe('one motion vocabulary', () => {
  it('exits shorter than it enters', () => {
    expect(motion.enter).toBe(180);
    expect(motion.exit).toBe(130);
    expect(motion.exit).toBeLessThan(motion.enter);
  });

  it('writes no hand-set duration literal in a timing call', () => {
    const hits = [];
    for (const [file, text] of sources) {
      for (const m of text.matchAll(/(?:timing|withTiming)\([^)]*?duration:\s*(\d+)/g)) {
        if (Number(m[1]) !== 0) hits.push(`${file}:${m[1]}`);
      }
    }
    expect(hits).toEqual([]);
  });

  it('uses the easing pair, never a hand-written bezier outside the token', () => {
    const hits = sources.filter(([file, text]) => /Easing\.bezier\(\s*\d/.test(text) && !file.endsWith('theme/tokens.js')).map(([file]) => file);
    expect(hits).toEqual([]);
  });

  it('runs every pulse on the shared half cadence', () => {
    for (const file of ['components/Dot.jsx', 'components/SkeletonBar.jsx', 'components/Fold.jsx', 'features/chat/ThinkingDots.jsx', 'features/chat/ToolCallRow.jsx', 'components/Toast.jsx', 'features/chat/SoundWave.jsx']) {
      const text = sources.find(([f]) => f === `src/${file}`)[1];
      expect(text, file).toMatch(/pulseSteps|PULSE_HALF_MS|motion\.pulse/);
    }
  });
});
