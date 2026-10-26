import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { detailTitleStyle } from './detailTitle';
import { fontSizes, lineHeights, tracking, typeLadder } from '../theme/tokens';

const read = (rel) => readFileSync(join(import.meta.dirname, '..', rel), 'utf8');
const theme = { colors: { ink: '#111' }, fonts: { sans: { semibold: 'sb' } }, fontSizes };

describe('detail H1 and eyebrow', () => {
  it('sets every detail title at the 22 pt ladder rung, distinct from the 18 pt screen title', () => {
    const style = detailTitleStyle(theme);
    expect(style.fontSize).toBe(typeLadder.detail);
    expect(style.fontSize).not.toBe(typeLadder.title);
    expect(style.letterSpacing).toBeCloseTo(typeLadder.detail * tracking.tight);
    expect(style.lineHeight).toBe(typeLadder.detail * lineHeights.cozy);
    expect(style.fontFamily).toBe('sb');
  });

  it.each([
    'features/brain/SkillDetail.jsx',
    'features/brain/ToolDetail.jsx',
    'features/brain/MemoryDetail.jsx',
    'features/schedule/JobDetail.jsx',
    'features/notifications/NotificationPage.jsx',
    'components/NotificationBody.jsx',
  ])('draws the %s title through detailTitleStyle', (file) => {
    expect(read(file)).toMatch(/detailTitleStyle\(/);
  });

  it('keeps one eyebrow tracking and no wider override', () => {
    expect(read('components/Eyebrow.jsx')).toMatch(/tracking\.eyebrow/);
    for (const file of ['components/Row.jsx', 'components/UsageChart.jsx']) {
      expect(read(file), file).not.toMatch(/tracking\.(wide|wider)\b/);
    }
  });
});
