import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { detailTitleStyle } from './detailTitle';
import { fontSizes, lineHeights, tracking, typeLadder } from '../theme/tokens';

const read = (rel) => readFileSync(join(import.meta.dirname, '..', rel), 'utf8');
const theme = { colors: { ink: '#111' }, fonts: { sans: { semibold: 'sb' } }, fontSizes };

describe('detail H1 and eyebrow', () => {
  it('sets every detail title at the 20 pt title rung, like every screen and sheet title', () => {
    const style = detailTitleStyle(theme);
    expect(style.fontSize).toBe(typeLadder.title);
    expect(style.fontSize).toBe(20);
    expect(style.letterSpacing).toBeCloseTo(typeLadder.title * tracking.tight);
    expect(style.lineHeight).toBe(typeLadder.title * lineHeights.cozy);
    expect(style.fontFamily).toBe('sb');
  });

  it.each([
    'components/DetailHead.jsx',
    'features/notifications/NotificationPage.jsx',
    'components/NotificationBody.jsx',
  ])('draws the %s title through detailTitleStyle', (file) => {
    expect(read(file)).toMatch(/detailTitleStyle\(/);
  });

  it('leaves section labels untracked and no wider override anywhere', () => {
    expect(read('components/Eyebrow.jsx')).not.toMatch(/letterSpacing|tracking/);
    for (const file of ['components/Row.jsx', 'components/UsageChart.jsx']) {
      expect(read(file), file).not.toMatch(/tracking\.(wide|wider)\b/);
    }
  });
});
