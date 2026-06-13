import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '../src/components/Button';
import { Diamond } from '../src/components/Diamond';
import { ScreenHeader } from '../src/components/ScreenHeader';
import { useToast } from '../src/components/Toast';
import { markAllUnifiedRead, useUnifiedOutputs } from '../src/hooks/useUnifiedOutputs';
import { useEndpoint } from '../src/lib/EndpointContext';
import { accentForProfile } from '../src/theme/accents';
import { useTheme } from '../src/theme/ThemeContext';
import { radii, space } from '../src/theme/tokens';


function fmtRelative(ts) {
  if (!ts) return '';
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.round(diff / 60)}m`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d`;
  return `${Math.round(diff / (86400 * 7))}w`;
}


function stripPreviewMarkdown(text) {
  return String(text || '')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/`{1,3}/g, '')
    .replace(/[*_~>#-]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}


function rowTitle(row) {
  const line = row.body?.split('\n').find((it) => stripPreviewMarkdown(it));
  return stripPreviewMarkdown(line) || '—';
}


export default function OutputsScreen() {
  const { colors, fonts, fontSizes } = useTheme();
  const router = useRouter();
  const { endpoint, connections, setActive } = useEndpoint();
  const toast = useToast();

  const [refreshing, setRefreshing] = useState(false);

  const { rows, loading, refresh } = useUnifiedOutputs();
  const multi = connections.length > 1;
  const unreadCount = useMemo(() => rows.filter((r) => r.status === 'unread').length, [rows]);

  useFocusEffect(useCallback(() => { refresh(); }, [refresh]));

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try { await refresh(); } finally { setRefreshing(false); }
  }, [refresh]);

  const onMarkAll = useCallback(async () => {
    const total = await markAllUnifiedRead(rows, connections);
    if (total) toast({ title: `Marked ${total} read` });
    refresh();
  }, [rows, connections, refresh, toast]);

  const openRow = useCallback(async (item) => {
    if (item.connectionId) {
      try { await setActive(item.connectionId); } catch { /* */ }
    }
    router.push({
      pathname: '/outputs/[profile]/[id]',
      params: { profile: item.profile, id: item.id, connectionId: item.connectionId ?? '' },
    });
  }, [router, setActive]);

  const renderRow = useCallback(({ item }) => {
    const accent = item.accent ?? accentForProfile(item.profile);
    const unread = item.status === 'unread';
    return (
      <Pressable
        onPress={() => openRow(item)}
        style={({ pressed }) => ({
          paddingHorizontal: space.s7,
          paddingVertical: space.s5,
          flexDirection: 'row',
          alignItems: 'flex-start',
          gap: space.s3,
          backgroundColor: pressed ? colors.selected : 'transparent',
        })}
        accessibilityLabel={rowTitle(item)}
      >
        <View
          style={{
            width: space.s2,
            height: space.s2,
            borderRadius: radii.pill,
            marginTop: space.s3,
            backgroundColor: unread ? accent : 'transparent',
          }}
        />
        <View style={{ flex: 1, minWidth: 0, gap: space.s2 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, flex: 1, minWidth: 0 }}>
              <Diamond color={accent} />
              <Text
                numberOfLines={1}
                style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}
              >
                @{item.profile}
              </Text>
              {multi ? (
                <Text
                  numberOfLines={1}
                  style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: accent }}
                >
                  · {item.connectionName}
                </Text>
              ) : null}
            </View>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
              {fmtRelative(item.created_at)}
            </Text>
          </View>
          <Text
            numberOfLines={1}
            style={{
              fontFamily: unread ? fonts.sans.semibold : fonts.sans.regular,
              fontSize: fontSizes.md,
              color: unread ? colors.ink : colors.ink3,
            }}
          >
            {rowTitle(item)}
          </Text>
        </View>
      </Pressable>
    );
  }, [colors, fonts, fontSizes, openRow, multi]);

  const showEmpty = !loading && rows.length === 0;
  const showSkeleton = loading && rows.length === 0;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Notifications"
        subtitle={unreadCount > 0 ? `${unreadCount} UNREAD` : 'INBOX ZERO'}
        onBack={() => router.back()}
        right={unreadCount > 0 ? (
          <Button title="Mark all read" size="md" variant="ghost" onPress={onMarkAll} />
        ) : null}
      />
      <FlatList
        style={{ flex: 1 }}
        data={rows}
        keyExtractor={(it) => `${it.connectionId}:${it.profile}:${it.id}`}
        renderItem={renderRow}
        ItemSeparatorComponent={() => (
          <View style={{ height: 0.5, backgroundColor: colors.line }} />
        )}
        contentContainerStyle={{ paddingBottom: space.s11, flexGrow: 1 }}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink3} />
        }
        ListEmptyComponent={
          showSkeleton ? (
            <View style={{ padding: space.s10, alignItems: 'center' }}>
              <ActivityIndicator color={colors.ink3} />
            </View>
          ) : showEmpty ? (
            <View
              style={{
                flex: 1,
                alignItems: 'center',
                justifyContent: 'center',
                padding: space.s10,
                gap: space.s3,
              }}
            >
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2 }}>
                Nothing here yet
              </Text>
              <Text
                style={{
                  fontFamily: fonts.sans.regular,
                  fontSize: fontSizes.md,
                  color: colors.ink3,
                  textAlign: 'center',
                }}
              >
                {endpoint
                  ? 'Notifications land here when your agent notifies you or a scheduled job fails.'
                  : 'Pair this phone to a daemon to see your notifications.'}
              </Text>
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
}
