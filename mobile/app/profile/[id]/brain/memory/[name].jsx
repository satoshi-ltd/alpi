import { useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../../src/theme/tokens';

import { Icon } from '../../../../../src/components/Icon';
import { RichText } from '../../../../../src/components/RichText';
import { PanelHeader } from '../../../../../src/features/profile/PanelHeader';
import { entryNote, memoryEntries, memoryFile } from '../../../../../../common/memoryEntries.mjs';
import { useBack } from '../../../../../src/hooks/useBack';
import { useDirtyBack } from '../../../../../src/hooks/useDirtyBack';
import { useMemoryEditor } from '../../../../../src/hooks/useMemoryEditor';
import { useTheme } from '../../../../../src/theme/ThemeContext';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function entryDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
  return m ? `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}` : String(iso || '');
}

export default function MemoryDetail() {
  const { id, name } = useLocalSearchParams();
  const file = memoryFile(String(name));
  const goBack = useBack();
  const { colors, fonts, fontSizes } = useTheme();
  const mem = useMemoryEditor(id, name);
  const askLeave = useDirtyBack(mem.dirty, goBack);

  async function onSave() {
    const res = await mem.save();
    if (res.ok) return;
    if (res.conflict) {
      Alert.alert('Changed elsewhere', 'This file changed since you opened it.', [
        { text: 'Keep editing', style: 'cancel' },
        { text: 'Reload (discard)', style: 'destructive', onPress: () => mem.reload() },
        {
          text: 'Overwrite',
          onPress: async () => {
            const r = await mem.save({ force: true });
            if (!r.ok && r.message) Alert.alert('Could not save', r.message);
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

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={[styles.safe, { backgroundColor: colors.bg }]}>
      <PanelHeader profile={id} section="MEMORIES" onBack={askLeave} right={right} />
      {mem.loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      ) : mem.loadError ? (
        <View style={styles.center}>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.dangerText, textAlign: 'center', padding: space.s8 }}>
            Couldn't load this file.{'\n'}{mem.loadError}
          </Text>
        </View>
      ) : mem.editing ? (
        <TextInput
          value={mem.draft}
          onChangeText={mem.setDraft}
          multiline
          autoCapitalize="none"
          autoCorrect={false}
          textAlignVertical="top"
          style={[styles.editor, mono]}
        />
      ) : (
        <ScrollView contentContainerStyle={styles.readBody}>
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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  actions: { flexDirection: 'row', gap: space.s2 },
  iconBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  editor: { flex: 1, padding: space.s8 },
  readBody: { padding: space.s8, gap: space.s6, paddingBottom: space.s10 },
});
