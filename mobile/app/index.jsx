import { useFocusEffect, usePathname, useRouter } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { DaemonBanner, isDaemonDown } from '../src/components/DaemonBanner';
import { ConnHeader } from '../src/features/inbox/ConnHeader';
import { InboxRow } from '../src/features/inbox/InboxRow';
import { Roster } from '../src/features/inbox/Roster';
import { RowContextSheet } from '../src/features/inbox/RowContextSheet';
import { ConnectionSheet } from '../src/features/sheets/ConnectionSheet';
import { CreateProfileSheet } from '../src/features/sheets/CreateProfileSheet';
import { CreateWorkgroupSheet } from '../src/features/sheets/CreateWorkgroupSheet';
import { useDebouncedCallback } from '../src/hooks/useDebouncedCallback';
import { useEventEffect } from '../src/hooks/useEvents';
import { useInbox } from '../src/hooks/useInbox';
import { useUnifiedOutputs } from '../src/hooks/useUnifiedOutputs';
import { useEndpoint } from '../src/lib/EndpointContext';
import { endpointHost } from '../src/lib/endpoint';
import { openVerb, OUTPUTS_PATH, SETTINGS_PATH, subjectPath } from '../src/lib/panes';
import { useFireOnce } from '../src/lib/useFireOnce';
import { usePins } from '../src/lib/pins';
import { useTheme } from '../src/theme/ThemeContext';
import { useCanAdminEarly } from '../src/hooks/useActiveRole';
import { HomePane } from '../src/features/shell/HomePane';
import { ShellFooter } from '../src/features/shell/ShellFooter';
import { useLaunchRestore } from '../src/features/shell/launchRestore';
import { NEW_PROFILE, NEW_WORKGROUP, useCreateGate } from '../src/features/shell/useCreateGate';
import { usePane } from '../src/nav/PaneContext';

function InboxScreen({ items, loading, refresh }) {
  const { colors } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const { twoPane } = usePane();
  const canAdmin = useCanAdminEarly();
  const { endpoint, probeState } = useEndpoint();
  const pins = usePins(endpoint?.id);
  const { rows: unreadOutputs } = useUnifiedOutputs({ status: 'unread' });
  const unreadCount = unreadOutputs.length;

  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const closeSearch = useCallback(() => { setSearchOpen(false); setQuery(''); }, []);
  const toggleSearch = useCallback(() => (searchOpen ? closeSearch() : setSearchOpen(true)), [searchOpen, closeSearch]);
  const [sheet, setSheet] = useState(null);
  const closeSheet = useCallback(() => setSheet(null), []);
  const canCreate = useCreateGate(sheet, closeSheet);
  const [ctxTarget, setCtxTarget] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh]),
  );

  const daemonStatus = endpoint ? probeState.get(endpoint.id) ?? 'unknown' : 'offline';

  const activeFailed = !!endpoint && isDaemonDown(daemonStatus);
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
    (item) => router.push(subjectPath(item)),
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

  const openSettings = useCallback(() => {
    setSheet(null);
    router[openVerb({ twoPane, pathname })](SETTINGS_PATH);
  }, [router, twoPane, pathname]);

  const openNotifications = useCallback(() => {
    setSheet(null);
    router[openVerb({ twoPane, pathname })](OUTPUTS_PATH);
  }, [router, twoPane, pathname]);

  const renderRow = useCallback(
    ({ item }) => <InboxRow item={item} onPress={openItem} onLongPress={handleLongPress} />,
    [openItem, handleLongPress],
  );

  const addActions = useMemo(
    () =>
      canCreate
        ? {
            profiles: { label: 'New profile', onPress: () => setSheet(NEW_PROFILE) },
            workgroups: { label: 'New workgroup', onPress: () => setSheet(NEW_WORKGROUP) },
          }
        : null,
    [canCreate],
  );

  return (
    <SafeAreaView edges={['top', 'left', 'right', 'bottom']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ConnHeader
        name={endpoint?.name ?? 'No daemon'}
        host={endpointHost(endpoint) || 'not paired'}
        status={daemonStatus}
        searchOpen={searchOpen}
        onToggleSearch={toggleSearch}
        onConnPress={() => setSheet('conn')}
      />
      <DaemonBanner status={daemonStatus} paired={!!endpoint} onRetry={onRefresh} />
      <Roster
        items={enriched}
        query={query}
        onQueryChange={setQuery}
        searchOpen={searchOpen}
        onCloseSearch={closeSearch}
        renderRow={renderRow}
        loading={loading}
        refreshing={refreshing}
        onRefresh={onRefresh}
        paired={!!endpoint}
        device="phone"
        addActions={addActions}
      />
      <ShellFooter
        unread={unreadCount}
        onNotificationsPress={canAdmin ? openNotifications : null}
        onSettingsPress={openSettings}
      />
      <ConnectionSheet open={sheet === 'conn'} onClose={closeSheet} />
      {canCreate ? (
        <>
          <CreateProfileSheet open={sheet === NEW_PROFILE} onClose={closeSheet} />
          <CreateWorkgroupSheet open={sheet === NEW_WORKGROUP} onClose={closeSheet} />
        </>
      ) : null}
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

export default function Index() {
  const { twoPane } = usePane();
  const { items, loading, refresh } = useInbox();
  useLaunchRestore({ items, twoPane });
  return twoPane ? <HomePane /> : <InboxScreen items={items} loading={loading} refresh={refresh} />;
}
