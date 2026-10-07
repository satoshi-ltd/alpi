import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, RefreshControl, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { EMPTY } from '../../common/emptyCopy.mjs';
import { headlineParts } from '../../common/notificationHeadline.mjs';
import {
  filterNotifications,
  groupNotifications,
  notificationKey,
  triageCounts,
} from '../../common/notificationTriage.mjs';
import { Button } from '../src/components/Button';
import { Eyebrow } from '../src/components/Eyebrow';
import { ScreenHeader } from '../src/components/ScreenHeader';
import { useToast } from '../src/components/Toast';
import { NotificationRow } from '../src/features/notifications/NotificationRow';
import { TriageFilters } from '../src/features/notifications/TriageFilters';
import { useBack } from '../src/hooks/useBack';
import { unreadMissingKey, useNotificationActions } from '../src/hooks/useOutputs';
import { adminConnectionsOf, isMemberOnly, markAllUnifiedRead, outputsEmptyState, outputsSubtitle, useUnifiedOutputs } from '../src/hooks/useUnifiedOutputs';
import { useEndpoint } from '../src/lib/EndpointContext';
import { freeze, setTrail, UNDO_MS, useNotificationStore, withKey } from '../src/lib/notificationStore';
import { clip } from '../src/lib/outputsFormat';
import { useTheme } from '../src/theme/ThemeContext';
import { space } from '../src/theme/tokens';
import { ListSkeleton } from '../src/components/ListSkeleton';

function keepWhere(set, keep) {
  const next = new Set([...set].filter(keep));
  return next.size === set.size ? set : next;
}

export default function OutputsScreen() {
  const { colors, fonts, fontSizes } = useTheme();
  const router = useRouter();
  const goBack = useBack();
  const { endpoint, connections, roleState, setActive, activeId } = useEndpoint();
  const toast = useToast();
  const actions = useNotificationActions();
  const { hidden, frozen, unreadMissing } = useNotificationStore();

  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState('all');
  const [readIds, setReadIds] = useState(() => new Set());
  const [unreadIds, setUnreadIds] = useState(() => new Set());

  const { rows, loading, refresh, hasAdmin, unreachable, unreachableCount } = useUnifiedOutputs();
  const adminConnections = useMemo(
    () => adminConnectionsOf(connections, roleState),
    [connections, roleState],
  );
  const multi = adminConnections.length > 1;

  useEffect(() => () => {
    freeze(null);
    setTrail(null);
  }, []);

  useEffect(() => {
    const status = new Map(rows.map((r) => [notificationKey(r), r.status]));
    setReadIds((prev) => keepWhere(prev, (k) => status.get(k) === 'unread'));
    setUnreadIds((prev) => keepWhere(prev, (k) => status.has(k) && status.get(k) !== 'unread'));
  }, [rows]);

  const isUnread = useCallback((r) => {
    const key = notificationKey(r);
    if (unreadIds.has(key)) return true;
    if (readIds.has(key)) return false;
    return r.status === 'unread';
  }, [readIds, unreadIds]);

  const visibleRows = useMemo(() => rows.filter((r) => !hidden.has(notificationKey(r))), [rows, hidden]);
  const unreadCount = useMemo(() => visibleRows.filter(isUnread).length, [visibleRows, isUnread]);
  const counts = useMemo(() => triageCounts(visibleRows, isUnread), [visibleRows, isUnread]);
  const shownRows = useMemo(() => filterNotifications(visibleRows, filter, { isUnread, frozen }), [visibleRows, filter, isUnread, frozen]);
  const groups = useMemo(() => groupNotifications(shownRows, { filter, isUnread, frozen }), [shownRows, filter, isUnread, frozen]);
  const items = useMemo(
    () => groups.flatMap((g) => [
      { kind: 'header', key: `h:${g.id}`, label: g.label },
      ...g.rows.map((row) => ({ kind: 'row', key: notificationKey(row), row, pinned: g.id === 'needs' })),
    ]),
    [groups],
  );

  useFocusEffect(useCallback(() => { refresh(); }, [refresh]));

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try { await refresh(); } finally { setRefreshing(false); }
  }, [refresh]);

  const onFilter = useCallback((id) => {
    freeze(null);
    setFilter(id);
  }, []);

  const onMarkAll = useCallback(async () => {
    setUnreadIds(new Set());
    setReadIds(new Set(rows.map(notificationKey)));
    const total = await markAllUnifiedRead(rows, adminConnections);
    if (total) toast({ title: `Marked ${total} read` });
    refresh();
  }, [rows, adminConnections, refresh, toast]);

  const openRow = useCallback(async (row) => {
    const entries = items
      .filter((it) => it.kind === 'row')
      .map((it) => ({
        key: it.key,
        profile: it.row.profile,
        id: it.row.id,
        connectionId: it.row.connectionId ?? '',
        pinned: it.pinned,
        unread: isUnread(it.row),
      }));
    setTrail(entries);
    freeze(entries.find((e) => e.key === notificationKey(row)) ?? null);
    if (row.connectionId) {
      try { await setActive(row.connectionId); } catch { /* */ }
    }
    router.push({
      pathname: '/outputs/[profile]/[id]',
      params: { profile: row.profile, id: row.id, connectionId: row.connectionId ?? '' },
    });
  }, [items, isUnread, router, setActive]);

  const canToggleRead = useCallback(
    (row) => !unreadMissing.has(unreadMissingKey(row.connectionId, activeId)),
    [unreadMissing, activeId],
  );

  const onToggleRead = useCallback(async (row) => {
    const key = notificationKey(row);
    if (isUnread(row)) {
      setUnreadIds((prev) => withKey(prev, key, false));
      setReadIds((prev) => withKey(prev, key, true));
      try {
        await actions.markRead(row);
      } catch (e) {
        setReadIds((prev) => withKey(prev, key, false));
        if (row.status === 'unread') setUnreadIds((prev) => withKey(prev, key, false));
        else setUnreadIds((prev) => withKey(prev, key, true));
        toast({ message: `Mark read failed: ${String(e?.message ?? e)}`, kind: 'danger' });
      }
    } else {
      setReadIds((prev) => withKey(prev, key, false));
      setUnreadIds((prev) => withKey(prev, key, true));
      try {
        const done = await actions.markUnread(row);
        if (!done) {
          setUnreadIds((prev) => withKey(prev, key, false));
          setReadIds((prev) => withKey(prev, key, true));
          toast({ message: 'This daemon cannot mark notifications unread.' });
        }
      } catch (e) {
        setUnreadIds((prev) => withKey(prev, key, false));
        setReadIds((prev) => withKey(prev, key, true));
        toast({ message: `Mark unread failed: ${String(e?.message ?? e)}`, kind: 'danger' });
      }
    }
    refresh();
  }, [isUnread, actions, toast, refresh]);

  const onDelete = useCallback((row) => {
    actions.remove(row, { onError: (e) => toast({ message: `Delete failed: ${String(e?.message ?? e)}`, kind: 'danger' }) });
    toast({
      message: `Deleted “${clip(headlineParts(row).title || 'notification', 48)}”`,
      action: 'Undo',
      onAction: () => actions.undoRemove(row),
      duration: UNDO_MS,
    });
  }, [actions, toast]);

  const renderItem = useCallback(({ item }) => {
    if (item.kind === 'header') {
      return (
        <Eyebrow accessibilityRole="header" style={{ paddingHorizontal: space.s7, paddingTop: space.s6, paddingBottom: space.s2 }}>
          {item.label}
        </Eyebrow>
      );
    }
    return (
      <NotificationRow
        row={item.row}
        unread={isUnread(item.row)}
        multi={multi}
        canToggleRead={canToggleRead(item.row)}
        onOpen={openRow}
        onToggleRead={onToggleRead}
        onDelete={onDelete}
      />
    );
  }, [isUnread, multi, canToggleRead, openRow, onToggleRead, onDelete]);

  const memberOnly = isMemberOnly(endpoint, connections, roleState);
  const empty = outputsEmptyState({
    memberOnly,
    hasAdmin,
    paired: !!endpoint,
    unreachable,
    unreachableCount,
    connectionCount: adminConnections.length,
  });
  const filtered = visibleRows.length > 0 && shownRows.length === 0;
  const emptyCopy = filtered ? { title: EMPTY.matches.title, detail: 'Nothing under this filter.' } : empty;
  const showSkeleton = loading && rows.length === 0;
  const showEmpty = !loading && items.length === 0;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Notifications"
        subtitle={outputsSubtitle({
          memberOnly,
          unreachable,
          unreachableCount,
          connectionCount: adminConnections.length,
          unreadCount,
          hasRows: visibleRows.length > 0,
        })}
        onBack={goBack}
        right={unreadCount > 0 ? (
          <Button title="Mark all read" size="md" variant="ghost" onPress={onMarkAll} />
        ) : null}
      />
      <FlatList
        style={{ flex: 1, backgroundColor: colors.bgPane }}
        data={items}
        keyExtractor={(it) => it.key}
        renderItem={renderItem}
        ListHeaderComponent={visibleRows.length > 0 ? (
          <TriageFilters
            filter={filter}
            counts={counts}
            onFilter={onFilter}
          />
        ) : null}
        contentContainerStyle={{ paddingBottom: space.s11, flexGrow: 1 }}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.ink3} />
        }
        ListEmptyComponent={
          showSkeleton ? (
            <ListSkeleton flat rows={5} label="Loading outputs" />
          ) : showEmpty || filtered ? (
            <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10, gap: space.s3 }}>
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2 }}>
                {emptyCopy.title}
              </Text>
              <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3, textAlign: 'center' }}>
                {emptyCopy.detail}
              </Text>
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
}
