import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (path) => readFileSync(join(import.meta.dirname, '..', path), 'utf8');

describe('readable placeholder ink', () => {
  it.each(['components/TextPrompt.jsx', 'components/ConfirmDialog.jsx', 'features/inbox/Roster.jsx', 'components/Field.jsx'])(
    '%s draws its placeholder in the secondary ink',
    (path) => {
      expect(read(path)).not.toMatch(/placeholderTextColor=\{colors\.ink4\}/);
      expect(read(path)).toMatch(/placeholderTextColor=\{colors\.ink3\}/);
    },
  );
});

describe('one picker lane', () => {
  it('starts the session picker separators at the text edge', () => {
    expect(read('features/sheets/SessionsSheet.jsx')).toMatch(/<RowSeparator indent=\{PICKER_TEXT_EDGE\} \/>/);
  });

  it('shares the lane between the action sheet and the picker row', () => {
    for (const path of ['components/ActionSheet.jsx', 'components/PickerRow.jsx']) {
      expect(read(path)).toMatch(/from '\.\/PickerLead'/);
      expect(read(path)).toMatch(/PICKER_GAP/);
    }
  });
});

describe('no platform alert for confirmations', () => {
  it.each(['hooks/useDirtyBack.js', 'features/brain/MemoryDetail.jsx', 'features/chat/AttachmentCards.jsx', 'features/sheets/ProfileFieldSheets.jsx'])(
    '%s never calls Alert.alert',
    (path) => {
      expect(read(path)).not.toMatch(/Alert\.alert/);
    },
  );
});

describe('toast levels at call sites', () => {
  it('leaves no numeric duration on a toast call outside the chat screens', () => {
    const files = ['features/settings/SettingsBody.jsx', 'features/sheets/EditBudgetSheet.jsx', 'features/sheets/CreateProfileSheet.jsx', 'features/shell/useActivityActions.js', 'hooks/usePullRefresh.js'];
    for (const path of files) expect(read(path)).not.toMatch(/duration: \d+/);
  });
});
