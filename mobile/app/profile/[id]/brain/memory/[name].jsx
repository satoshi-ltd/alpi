import { useLocalSearchParams, useRouter } from 'expo-router';
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../../src/theme/tokens';

import { Icon } from '../../../../../src/components/Icon';
import { ScreenHeader } from '../../../../../src/components/ScreenHeader';
import { useDirtyBack } from '../../../../../src/hooks/useDirtyBack';
import { useMemoryEditor } from '../../../../../src/hooks/useMemoryEditor';
import { useTheme } from '../../../../../src/theme/ThemeContext';

function stripMemoryDelimiters(text) {
  return text.replace(/^§$/gm, '').replace(/\n{3,}/g, '\n\n');
}

export default function MemoryDetail() {
  const { id, name, label, helper } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const mem = useMemoryEditor(id, name);
  const askLeave = useDirtyBack(mem.dirty, () => router.back());

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

  const mono = { fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * 1.55, color: colors.ink };
  const iconBtn = (icon, onPress) => (
    <Pressable onPress={onPress} hitSlop={space.s3} style={styles.iconBtn}>
      <Icon name={icon} size={20} color={colors.ink2} strokeWidth={2} />
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
      <ScreenHeader
        title={String(label ?? name ?? 'Memory')}
        subtitle={String(helper ?? `@${id}`)}
        onBack={askLeave}
        right={right}
      />
      {mem.loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      ) : mem.loadError ? (
        <View style={styles.center}>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.danger, textAlign: 'center', padding: space.s8 }}>
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
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
            memories/{String(name)}
          </Text>
          <Text style={mono}>{stripMemoryDelimiters(mem.raw) || '(empty)'}</Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  actions: { flexDirection: 'row', gap: space.s2 },
  iconBtn: { width: 28, height: 36, alignItems: 'center', justifyContent: 'center' },
  editor: { flex: 1, padding: space.s8 },
  readBody: { padding: space.s8, gap: space.s3, paddingBottom: space.s10 },
});
