import { useEffect } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../theme/tokens';

import { AlertBanner } from '../../components/AlertBanner';
import { useAttention } from '../../hooks/useAttention';
import { memoryBanner, memoryItem } from '../../../../common/attention.mjs';
import { Icon } from '../../components/Icon';
import { KeyboardPane } from '../../components/KeyboardPane';
import { RichText } from '../../components/RichText';
import { PanelHeader } from '../profile/PanelHeader';
import { entryNote, memoryEntries, memoryFile } from '../../../../common/memoryEntries.mjs';
import { useDirtyBack } from '../../hooks/useDirtyBack';
import { useMemoryEditor } from '../../hooks/useMemoryEditor';
import { useTheme } from '../../theme/ThemeContext';
import { ReaderSkeleton } from '../../components/ReaderSkeleton';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function entryDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
  return m ? `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}` : String(iso || '');
}

export function MemoryDetail({ profile: id, name, embedded = false, onBack, onDirtyChange, onSaved }) {
  const file = memoryFile(String(name));
  const { colors, fonts, fontSizes } = useTheme();
  const mem = useMemoryEditor(id, name);
  const { att } = useAttention(id);
  const flag = memoryItem(att, String(name));
  const askLeave = useDirtyBack(mem.dirty, onBack ?? (() => {}));
  useEffect(() => {
    onDirtyChange?.(mem.dirty);
    return () => onDirtyChange?.(false);
  }, [mem.dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  async function onSave() {
    const res = await mem.save();
    if (res.ok) {
      onSaved?.();
      return;
    }
    if (res.conflict) {
      Alert.alert('Changed elsewhere', 'This file changed since you opened it.', [
        { text: 'Keep editing', style: 'cancel' },
        { text: 'Reload (discard)', style: 'destructive', onPress: () => mem.reload() },
        {
          text: 'Overwrite',
          onPress: async () => {
            const r = await mem.save({ force: true });
            if (r.ok) onSaved?.();
            else if (r.message) Alert.alert('Could not save', r.message);
          },
        },
      ]);
    } else if (res.message) {
      Alert.alert('Could not save', res.message);
    }
  }

  const entries = memoryEntries(mem.raw ?? '');
  const mono = { fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * 1.55, color: colors.ink };
  const iconBtn = (icon, onPress) => (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={icon === 'edit' ? 'Edit' : icon === 'check' ? 'Save' : 'Cancel'} style={styles.iconBtn}>
      <Icon name={icon} size="lg" color={colors.ink2} />
    </Pressable>
  );

  const right = mem.editing ? (
    <View style={styles.actions}>
      {iconBtn('check', onSave)}
      {iconBtn('x', mem.cancel)}
    </View>
  ) : mem.canEdit ? (
    iconBtn('edit', mem.startEdit)
  ) : null;

  const Shell = embedded ? View : SafeAreaView;
  const shellProps = embedded ? { style: [styles.safe, { backgroundColor: colors.bg }] } : { edges: ['top', 'left', 'right'], style: [styles.safe, { backgroundColor: colors.bg }] };

  return (
    <Shell {...shellProps}>
      {embedded ? (
        <View style={styles.toolbar}>{right}</View>
      ) : (
        <PanelHeader profile={id} section="MEMORIES" onBack={askLeave} right={right} />
      )}
      {mem.loading ? (
        <ReaderSkeleton label="Loading the memory file" />
      ) : mem.loadError ? (
        <View style={styles.center}>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.dangerText, textAlign: 'center', padding: space.s8 }}>
            Couldn't load this file.{'\n'}{mem.loadError}
          </Text>
        </View>
      ) : mem.editing ? (
        <KeyboardPane>
          <TextInput
            value={mem.draft}
            onChangeText={mem.setDraft}
            multiline
            autoCapitalize="none"
            autoCorrect={false}
            textAlignVertical="top"
            style={[styles.editor, mono]}
          />
        </KeyboardPane>
      ) : (
        <ScrollView contentContainerStyle={styles.readBody}>
          {flag ? <AlertBanner {...memoryBanner(flag)} /> : null}
          <View style={{ gap: space.s1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.s3 }}>
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink }}>{file.label}</Text>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{String(name)}</Text>
            </View>
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>{file.caption(String(id))}</Text>
          </View>
          {entries.length === 0 ? (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>(empty)</Text>
          ) : entries.map((entry, i) => (
            <View key={i} style={{ gap: space.s2 }}>
              <RichText size={fontSizes.md} color={colors.ink}>{entry.text}</RichText>
              {entryNote(entry, entryDate) ? (
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{entryNote(entry, entryDate)}</Text>
              ) : null}
            </View>
          ))}
        </ScrollView>
      )}
    </Shell>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  actions: { flexDirection: 'row', gap: space.s2 },
  toolbar: { flexDirection: 'row', justifyContent: 'flex-end', minHeight: 44, paddingHorizontal: space.s5 },
  iconBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  editor: { flex: 1, padding: space.s8 },
  readBody: { padding: space.s8, gap: space.s6, paddingBottom: space.s10 },
});
