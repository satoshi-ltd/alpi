import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';
import { RefreshControl, ScrollView, View } from 'react-native';
import { space } from '../../theme/tokens';

import { useAttention } from '../../hooks/useAttention';
import { memoryItem, memoryWord } from '../../../../common/attention.mjs';
import { RowGroup, SectionHeader, RowSeparator } from '../../components/Row';
import { MEMORY_FILES } from '../../../../common/memoryEntries.mjs';
import { memoryMeta, memoryShare } from '../../../../common/panelRow.mjs';
import { PanelRow } from '../../components/PanelRow';
import { useProfileMemory } from '../../hooks/useDaemonData';
import { usePullRefresh } from '../../hooks/usePullRefresh';
import { useTheme } from '../../theme/ThemeContext';
import { LoadFailed } from '../../components/LoadFailed';
import { ListSkeleton } from '../../components/ListSkeleton';
import { useSkeleton } from '../../hooks/useSkeleton';
import { useReveal } from '../../hooks/useReveal';
import { FadeIn } from '../../components/FadeIn';

export function MemoryList({ profile: id, selectedFile = null, refreshKey = 0, onOpen }) {
  const { colors } = useTheme();
  const pull = usePullRefresh(() => mem.refresh?.());
  const mem = useProfileMemory(id);
  const { att } = useAttention(id);
  const needs = MEMORY_FILES.filter((f) => memoryItem(att, f.file));
  const pending = mem.loading && !mem.data;
  const bones = useSkeleton(pending);
  const revealed = useReveal(bones);
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
      {bones ? (
        <ListSkeleton rows={4} helper="sm" label="Loading memories" style={{ marginTop: space.s5 }} />
      ) : pending ? null : <FadeIn animate={revealed}>{mem.error && !mem.data ? (
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
                  const word = flag ? memoryWord(flag) : u?.over ? 'over' : null;
                  const { meta, tone } = memoryMeta(u?.used, u?.limit, word);
                  const pct = memoryShare(u?.used, u?.limit);
                  return (
                    <View key={f.file}>
                      {i > 0 ? <RowSeparator /> : null}
                      <PanelRow
                        title={f.label}
                        sub={f.caption(String(id))}
                        meta={meta}
                        metaTone={tone}
                        bar={pct == null ? null : { pct, over: !!u?.over || !!flag?.over }}
                        selected={f.file === selectedFile}
                        onPress={() => onOpen(f.file)}
                        accessibilityLabel={[f.label, f.file, meta].filter(Boolean).join(', ')}
                      />
                    </View>
                  );
                })}
              </RowGroup>
            </View>
          ))}
        </>
      )}</FadeIn>}
    </ScrollView>
  );
}
