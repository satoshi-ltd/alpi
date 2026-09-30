import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { ENTER_MS } from '../src/features/chat/chatMotion.jsx';

const ROOT = join(import.meta.dirname, '..');
const SCREENS = ['app/chat/[id].jsx', 'app/wg/[id].jsx'];

describe('chat list motion', () => {
  it.each(SCREENS)('%s drags the keyboard away with the list', (file) => {
    expect(readFileSync(join(ROOT, file), 'utf8')).toMatch(/keyboardDismissMode=\{listDismissMode\(\)\}/);
  });

  it.each(SCREENS)('%s fades in only appended rows, and nothing under reduced motion', (file) => {
    const src = readFileSync(join(ROOT, file), 'utf8');
    expect(src).toMatch(/<EnterOnce[\s\S]*?fresh=\{!reduceMotion && /);
    expect(src).toMatch(/useSeenIds\(/);
  });

  it('keeps the entrance inside the 150–200 ms band', () => {
    expect(ENTER_MS).toBeGreaterThanOrEqual(150);
    expect(ENTER_MS).toBeLessThanOrEqual(200);
  });
});
