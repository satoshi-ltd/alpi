import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useRef } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../../src/theme/tokens';

import { RowGroup, RowSeparator } from '../../../../../src/components/Row';
import { PanelHeader } from '../../../../../src/features/profile/PanelHeader';
import { MEMORY_FILES, memoryEntries } from '../../../../../../common/memoryEntries.mjs';
import { useBack } from '../../../../../src/hooks/useBack';
import { useProfileMemory } from '../../../../../src/hooks/useDaemonData';
import { usePullRefresh } from '../../../../../src/hooks/usePullRefresh';
import { useTheme } from '../../../../../src/theme/ThemeContext';
import { LoadFailed } from '../../../../../src/components/LoadFailed';

function Meter({ used, limit, over }) {
  const { colors, fonts, fontSizes } = useTheme();
  if (used == null || !limit) return null;
  const pct = Math.min(100, Math.round((used / limit) * 100));
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4 }}>
      <View style={{ flex: 1, height: 3, borderRadius: 2, backgroundColor: colors.hover, overflow: 'hidden' }}>
        <View style={{ width: `${pct}%`, height: 3, backgroundColor: over ? colors.danger : colors.ink2 }} />
      </View>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: over ? colors.dangerText : colors.ink3 }}>
        {`${used.toLocaleString('en-US')} / ${limit.toLocaleString('en-US')}`}
      </Text>
    </View>
  );
}

export default function MemoryList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors, fonts, fontSizes } = useTheme();
  const pull = usePullRefresh(() => mem.refresh?.());
  const mem = useProfileMemory(id);
  const refresh = mem.refresh;
  const settled = useRef(false);
  useFocusEffect(useCallback(() => {
    if (settled.current) refresh();
    else settled.current = true;
  }, [refresh]));

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader profile={id} section="MEMORIES" count={MEMORY_FILES.length} onBack={goBack} />
      <ScrollView refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />} contentContainerStyle={{ paddingBottom: space.s9 }}>
        {mem.loading && !mem.data ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : mem.error && !mem.data ? (
          <LoadFailed inline label="memories" error={mem.error} onRetry={() => mem.refresh?.()} />
        ) : (
          <RowGroup style={{ marginTop: space.s5 }}>
            {MEMORY_FILES.map((f, i) => {
              const u = mem.usage?.[f.file];
              const raw = mem.data?.[f.file] ?? '';
              const count = /\n§\n/.test(raw) ? memoryEntries(raw).length : null;
              return (
                <View key={f.file}>
                  {i > 0 ? <RowSeparator /> : null}
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`${f.label}, ${f.file}`}
                    onPress={() => router.push({ pathname: `/profile/${id}/brain/memory/[name]`, params: { name: f.file } })}
                    android_ripple={{ color: colors.selected }}
                    style={({ pressed }) => ({
                      minHeight: 44,
                      paddingHorizontal: space.s8,
                      paddingVertical: space.s5,
                      gap: space.s2,
                      backgroundColor: pressed ? colors.selected : 'transparent',
                    })}
                  >
                    <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.s3 }}>
                      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}>{f.label}</Text>
                      <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{f.file}</Text>
                      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{count ? `${count} ${count === 1 ? 'entry' : 'entries'}` : raw.trim() ? '' : 'empty'}</Text>
                    </View>
                    <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>{f.caption(String(id))}</Text>
                    <Meter used={u?.used ?? null} limit={u?.limit ?? null} over={!!u?.over} />
                  </Pressable>
                </View>
              );
            })}
          </RowGroup>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
