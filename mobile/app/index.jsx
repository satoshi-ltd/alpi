import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../src/theme/tokens';

import { Banner } from '../src/components/Banner';
import { Icon } from '../src/components/Icon';
import { Swipeable } from '../src/components/Swipeable';
import { ConnHeader } from '../src/features/inbox/ConnHeader';
import { InboxRow } from '../src/features/inbox/InboxRow';
import { InboxSkeleton } from '../src/features/inbox/InboxSkeleton';
import { PinnedRow } from '../src/features/inbox/PinnedRow';
import { RowContextSheet } from '../src/features/inbox/RowContextSheet';
import { SegmentedFilter } from '../src/features/inbox/SegmentedFilter';
import { ComposeSheet } from '../src/features/sheets/ComposeSheet';
import { ConnectionSheet } from '../src/features/sheets/ConnectionSheet';
import { SettingsSheet } from '../src/features/sheets/SettingsSheet';
import { useDebouncedCallback } from '../src/hooks/useDebouncedCallback';
import { useEventEffect } from '../src/hooks/useEvents';
import { useInbox } from '../src/hooks/useInbox';
import { useUnifiedOutputs } from '../src/hooks/useUnifiedOutputs';
import { useEndpoint } from '../src/lib/EndpointContext';
import { useFireOnce } from '../src/lib/useFireOnce';
import { usePins } from '../src/lib/pins';
import { useTheme } from '../src/theme/ThemeContext';
import { useCanAdminEarly } from '../src/hooks/useActiveRole';

export default function Inbox() {
  const { colors, fonts, fontSizes } = useTheme();
  const router = useRouter();
  const canAdmin = useCanAdminEarly();
  const { endpoint, probeState } = useEndpoint();
  const { items, loading, refresh } = useInbox();
  const pins = usePins(endpoint?.id);
  const { rows: unreadOutputs } = useUnifiedOutputs({ status: 'unread' });
  const unreadCount = unreadOutputs.length;

  const [tab, setTab] = useState('all');
  const [sheet, setSheet] = useState(null);
  const [ctxTarget, setCtxTarget] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Focus refresh — useProfileSummaries is per-consumer, so create-screen's refresh doesn't reach here.
  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  const daemonStatus = endpoint ? probeState.get(endpoint.id) ?? 'unknown' : 'offline';

  const activeFailed =
    !!endpoint && (
      daemonStatus === 'offline' ||
      daemonStatus === 'disabled' ||
      daemonStatus === 'auth-failed'
    );
  useFireOnce(activeFailed, () => setSheet('conn'));

  const enriched = useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const it of items) {
      const key = `${it.kind}:${it.kind === 'workgroup' ? `${it.profile}/` : ''}${it.id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        ...it,
        pinned: it.kind === 'profile'
          ? pins.isProfilePinned(it.name)
          : pins.isWorkgroupPinned(it.profile, it.id),
      });
    }
    return out;
  }, [items, pins]);

  // Pinned excluded from list — top strip already shows them with unread pip + accent.
  const unpinned = useMemo(() => enriched.filter((it) => !it.pinned), [enriched]);

  const filtered = useMemo(() => {
    if (tab === 'alpis') return unpinned.filter((it) => it.kind === 'profile');
    if (tab === 'wg') return unpinned.filter((it) => it.kind === 'workgroup');
    return unpinned;
  }, [unpinned, tab]);

  const pinned = useMemo(() => enriched.filter((it) => it.pinned), [enriched]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);

  // Coalesced: a busy workgroup or a reconnect backfill emits bursts — one summaries+workgroups refresh per beat, not per event.
  const debouncedRefresh = useDebouncedCallback(refresh, 800);
  useEventEffect(
    [
      'session_changed',
      'wg.post',
      'wg.done',
      'schedule.done',
      'schedule.failed',
      // Cross-device mutations propagate via these events — avoids polling.
      'workgroup_changed',
      'workgroup_members',
      'profile_changed',
      'peers_changed',
    ],
    debouncedRefresh,
  );

  const openItem = useCallback(
    (item) => {
      const path = item.kind === 'workgroup' ? `/wg/${item.id}` : `/chat/${item.id}`;
      router.push(path);
    },
    [router],
  );

  const togglePin = useCallback(
    (item) => {
      if (item.kind === 'profile') pins.toggleProfile(item.name);
      else pins.toggleWorkgroup(item.profile, item.id);
    },
    [pins],
  );

  // Stable refs — InboxRow is memo()d, fresh arrows per row would defeat it.
  const handleLongPress = useCallback((item) => setCtxTarget(item), []);

  const renderRow = useCallback(
    ({ item }) => (
      <Swipeable
        leftActions={[
          {
            id: 'pin',
            label: item.pinned ? 'Unpin' : 'Pin',
            tone: 'warning',
            icon: <Icon name="plus" size={20} color={colors.bgPane} strokeWidth={2} />,
            onPress: () => togglePin(item),
          },
        ]}
      >
        <InboxRow item={item} onPress={openItem} onLongPress={handleLongPress} />
      </Swipeable>
    ),
    [colors.bgPane, togglePin, openItem, handleLongPress],
  );

  // Constant row height → getItemLayout skips measure pass on long lists.
  const ROW_HEIGHT = 64;
  const SEPARATOR_HEIGHT = 0.5;
  const getItemLayout = useCallback(
    (_data, index) => ({
      length: ROW_HEIGHT,
      offset: (ROW_HEIGHT + SEPARATOR_HEIGHT) * index,
      index,
    }),
    [],
  );

  const showEmpty = !loading && filtered.length === 0;
  const showSkeleton = loading && filtered.length === 0;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ConnHeader
        name={endpoint?.name ?? 'No daemon'}
        host={endpoint ? `${endpoint.ip}:${endpoint.port}` : 'not paired'}
        status={daemonStatus}
        unread={canAdmin ? unreadCount : 0}
        onConnPress={() => setSheet('conn')}
        onBellPress={canAdmin ? () => router.push('/outputs') : null}
        onGearPress={() => setSheet('settings')}
      />
      {daemonStatus === 'offline' && endpoint ? (
        <Banner kind="danger" action="Retry" onAction={onRefresh}>
          Daemon unreachable. Reconnecting…
        </Banner>
      ) : daemonStatus === 'disabled' && endpoint ? (
        <Banner kind="warning">
          Connection disabled by host. Ask an admin to enable it in Settings → Connections.
        </Banner>
      ) : null}
      <PinnedRow items={pinned} onPress={openItem} onLongPress={setCtxTarget} />
      <View style={{ marginHorizontal: space.s7, marginBottom: space.s3 }}>
        <SegmentedFilter value={tab} onChange={setTab} />
      </View>
      <FlatList
        style={{ flex: 1 }}
        data={filtered}
        keyExtractor={(it) => `${it.kind}:${it.kind === 'workgroup' ? `${it.profile}/` : ''}${it.id}`}
        renderItem={renderRow}
        getItemLayout={getItemLayout}
        ItemSeparatorComponent={() => (
          <View style={{ height: SEPARATOR_HEIGHT, backgroundColor: colors.line, marginLeft: 64 }} />
        )}
        contentContainerStyle={{ paddingBottom: 120, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink3} />}
        ListEmptyComponent={
          showSkeleton ? (
            <InboxSkeleton />
          ) : showEmpty ? (
            <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10, gap: space.s3, minHeight: 240 }}>
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2 }}>
                What's on your mind?
              </Text>
              <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3, textAlign: 'center' }}>
                {endpoint
                  ? tab === 'wg'
                    ? 'No workgroups yet.'
                    : tab === 'alpis'
                      ? 'No alpis on this daemon yet. Tap + to create one.'
                      : 'Empty inbox.'
                  : 'Pair this phone to a daemon to see your alpis.'}
              </Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          loading && filtered.length > 0 ? (
            <View style={{ padding: space.s9, alignItems: 'center' }}>
              <ActivityIndicator color={colors.ink3} />
            </View>
          ) : null
        }
      />
      <Pressable
        onPress={() => setSheet('compose')}
        style={({ pressed }) => ({
          position: 'absolute',
          right: 16,
          bottom: 16,
          width: 56,
          height: 56,
          borderRadius: radii.xl,
          backgroundColor: pressed ? colors.ink2 : colors.ink,
          alignItems: 'center',
          justifyContent: 'center',
          shadowColor: '#000',
          shadowOffset: { width: 0, height: 8 },
          shadowOpacity: 0.2,
          shadowRadius: 24,
          elevation: 8,
        })}
        accessibilityLabel="Compose"
      >
        <Icon name="plus" size={22} color={colors.bgPane} strokeWidth={2} />
      </Pressable>

      <ConnectionSheet open={sheet === 'conn'} onClose={() => setSheet(null)} />
      <SettingsSheet open={sheet === 'settings'} onClose={() => setSheet(null)} />
      <ComposeSheet open={sheet === 'compose'} onClose={() => setSheet(null)} />
      <RowContextSheet
        target={ctxTarget}
        onClose={() => setCtxTarget(null)}
        onPin={togglePin}
        onOpenSettings={canAdmin ? (t) => {
          setCtxTarget(null);
          router.push(t.kind === 'workgroup' ? `/wg/${t.id}/settings` : `/profile/${t.id}/settings`);
        } : null}
      />
    </SafeAreaView>
  );
}
