import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { dotShape } from './dotShape';

const ROOT = join(import.meta.dirname, '..', '..');
const source = (path) => readFileSync(join(ROOT, path), 'utf8');

describe('dotShape', () => {
  it('draws only the 6 pt inline dot and the 8 pt attention dot', () => {
    expect(dotShape('sm')).toEqual({ width: 6, height: 6, borderRadius: 3 });
    expect(dotShape('md')).toEqual({ width: 8, height: 8, borderRadius: 4 });
  });
});

describe('dots on the ladder', () => {
  it.each([
    'src/features/chat/ChatHeader.jsx',
    'src/components/ActionSheet.jsx',
  ])('%s draws its attention dot at 8 pt with no ring', (path) => {
    const text = source(path);
    expect(text).toMatch(/\.\.\.dotShape\('md'\), backgroundColor: colors\.danger \}/);
    expect(text).not.toMatch(/borderWidth: 1\.5, borderColor: colors\.(bg|bgPane) \}/);
  });

  it.each([
    'src/components/Dot.jsx',
    'src/components/Pill.jsx',
    'src/features/inbox/RowState.jsx',
    'src/features/notifications/NotificationRow.jsx',
    'src/features/settings/SectionJump.jsx',
    'src/features/chat/ThinkingDots.jsx',
  ])('%s takes its dot from the scale instead of a literal', (path) => {
    expect(source(path)).toMatch(/dotShape\(/);
    expect(source(path)).not.toMatch(/dotSize|width: 6, height: 6|width: 7, height: 7/);
  });
});
