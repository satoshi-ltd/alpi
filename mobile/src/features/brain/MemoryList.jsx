import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { space } from '../../theme/tokens';

import { Dot } from '../../components/Dot';
import { useAttention } from '../../hooks/useAttention';
import { memoryItem, memoryWord } from '../../../../common/attention.mjs';
import { RowGroup, SectionHeader, RowSeparator } from '../../components/Row';
import { MEMORY_FILES, memoryEntries } from '../../../../common/memoryEntries.mjs';
import { useProfileMemory } from '../../hooks/useDaemonData';
import { usePullRefresh } from '../../hooks/usePullRefresh';
import { useTheme } from '../../theme/ThemeContext';
import { LoadFailed } from '../../components/LoadFailed';
import { ListSkeleton } from '../../components/ListSkeleton';

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

export function MemoryList({ profile: id, selectedFile = null, refreshKey = 0, onOpen }) {
  const { colors, fonts, fontSizes } = useTheme();
  const pull = usePullRefresh(() => mem.refresh?.());
  const mem = useProfileMemory(id);
  const { att } = useAttention(id);
  const needs = MEMORY_FILES.filter((f) => memoryItem(att, f.file));
  const refresh = mem.refresh;
  const settled = useRef(false);
  const firstKey = useRef(refreshKey);
  useEffect(() => {
    if (refreshKey !== firstKey.current) refresh();
  }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useFocusEffect(useCallback(() => {
    if (settled.current) refresh();
    else settled.current = true;
  }, [refresh]));

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />} contentContainerStyle={{ paddingBottom: space.s9 }}>
      {mem.loading && !mem.data ? (
        <ListSkeleton rows={4} helper="sm" label="Loading memories" style={{ marginTop: space.s5 }} />
      ) : mem.error && !mem.data ? (
        <LoadFailed inline label="memories" error={mem.error} onRetry={() => mem.refresh?.()} />
      ) : (
        <>
          {[['Needs you', needs], ['', MEMORY_FILES.filter((f) => !memoryItem(att, f.file))]].map(([label, files]) => files.length === 0 ? null : (
            <View key={label || 'rest'}>
              {label ? <SectionHeader>{`${label} · ${files.length}`}</SectionHeader> : null}
              <RowGroup style={!label && needs.length === 0 ? { marginTop: space.s5 } : undefined}>
                {files.map((f, i) => {
                  const flag = memoryItem(att, f.file);
                  const u = mem.usage?.[f.file];
                  const raw = mem.data?.[f.file] ?? '';
                  const count = /\n§\n/.test(raw) ? memoryEntries(raw).length : null;
                  return (
                    <View key={f.file}>
                      {i > 0 ? <RowSeparator /> : null}
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={flag ? `${f.label}, ${f.file}, ${memoryWord(flag)}` : `${f.label}, ${f.file}`}
                        onPress={() => onOpen(f.file)}
                        android_ripple={{ color: colors.selected }}
                        accessibilityState={{ selected: f.file === selectedFile }}
                        style={({ pressed }) => ({
                          minHeight: 44,
                          paddingHorizontal: space.s8,
                          paddingVertical: space.s5,
                          gap: space.s2,
                          backgroundColor: pressed || f.file === selectedFile ? colors.selected : 'transparent',
                        })}
                      >
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                          {flag ? <Dot color={colors.danger} /> : null}
                          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}>{f.label}</Text>
                          <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{f.file}</Text>
                          {flag ? (
                            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.dangerText }}>{memoryWord(flag)}</Text>
                          ) : (
                            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{count ? `${count} ${count === 1 ? 'entry' : 'entries'}` : raw.trim() ? '' : 'empty'}</Text>
                          )}
                        </View>
                        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>{f.caption(String(id))}</Text>
                        <Meter used={u?.used ?? null} limit={u?.limit ?? null} over={!!u?.over} />
                      </Pressable>
                    </View>
                  );
                })}
              </RowGroup>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}
