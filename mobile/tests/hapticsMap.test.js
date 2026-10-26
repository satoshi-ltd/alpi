import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (rel) => readFileSync(join(import.meta.dirname, '..', rel), 'utf8');

describe('haptics map', () => {
  it('taps on a swipe commit', () => {
    const source = read('src/features/notifications/NotificationRow.jsx');
    expect(source).toMatch(/import \{ tap \} from '..\/..\/lib\/haptics'/);
    expect(source).toMatch(/const act = \(fn\) => \(\) => \{\s*tap\(\);/);
  });

  it('taps on pin and unpin', () => {
    const source = read('src/features/inbox/RowContextSheet.jsx');
    expect(source).toMatch(/tap\(\);\s*onPin\?\.\(target\)/);
  });

  it('ticks a selection on pickers, toggles, action sheets and dialogs', () => {
    for (const file of ['components/PickerRow.jsx', 'components/Toggle.jsx', 'components/ActionSheet.jsx', 'components/ConfirmDialog.jsx']) {
      expect(read(`src/${file}`), file).toMatch(/selection\(\)/);
    }
  });
});
