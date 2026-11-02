import { readdirSync, readFileSync, statSync } from 'node:fs';
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

function sources(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return sources(full);
    return /\.jsx?$/.test(name) && !name.includes('.test.') ? [full] : [];
  });
}

describe('readable text ink', () => {
  it('never sets text in ink4, which stays for rules, grabbers and disabled marks', () => {
    const root = join(import.meta.dirname, '..', '..');
    const offenders = ['app', 'src'].flatMap((dir) => sources(join(root, dir)))
      .filter((file) => /(^|[^A-Za-z])color:\s*colors\.ink4\b/.test(readFileSync(file, 'utf8')));
    expect(offenders).toEqual([]);
  });
});

describe('rows say they are buttons', () => {
  it.each([
    'features/brain/ToolsList.jsx',
    'features/brain/SkillsList.jsx',
    'features/sheets/TasksSheet.jsx',
    '../app/profile/[id]/email/index.jsx',
    '../app/profile/[id]/email/[aid].jsx',
    '../app/profile/[id]/mcp/index.jsx',
    '../app/wg/[id]/member.jsx',
  ])('%s gives every Pressable a role', (path) => {
    const src = read(path);
    const pressables = src.split('<Pressable').slice(1).map((chunk) => chunk.slice(0, chunk.indexOf('style=')));
    expect(pressables.length).toBeGreaterThan(0);
    for (const props of pressables) expect(props).toMatch(/accessibilityRole=/);
  });
});

describe('toggles say whether they are on', () => {
  it('announces each workgroup member chip as a checkbox with its state', () => {
    const src = read('features/sheets/CreateWorkgroupSheet.jsx');
    expect(src).toMatch(/accessibilityRole="checkbox"\s+accessibilityState=\{\{ checked: on \}\}/);
  });
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
