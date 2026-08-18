import { usePathname, useRouter } from 'expo-router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppState } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../theme/tokens';

import { Banner } from '../../components/Banner';
import { ConnHeader } from '../inbox/ConnHeader';
import { InboxRow } from '../inbox/InboxRow';
import { Roster } from '../inbox/Roster';
import { RowContextSheet } from '../inbox/RowContextSheet';
import { ConnectionSheet } from '../sheets/ConnectionSheet';
import { CreateProfileSheet } from '../sheets/CreateProfileSheet';
import { CreateWorkgroupSheet } from '../sheets/CreateWorkgroupSheet';
import { ShellFooter } from './ShellFooter';
import { useCanAdminEarly } from '../../hooks/useActiveRole';
import { useDebouncedCallback } from '../../hooks/useDebouncedCallback';
import { useEventEffect } from '../../hooks/useEvents';
import { useInbox } from '../../hooks/useInbox';
import { useUnifiedOutputs } from '../../hooks/useUnifiedOutputs';
import { useEndpoint } from '../../lib/EndpointContext';
import { endpointHost } from '../../lib/endpoint';
import { OUTPUTS_PATH, SETTINGS_PATH, SIDEBAR_W, openVerb, sidebarSelection } from '../../lib/panes';
import { usePins } from '../../lib/pins';
import { useFireOnce } from '../../lib/useFireOnce';
import { NEW_PROFILE, NEW_WORKGROUP, useCreateGate } from './useCreateGate';
import { PaneContext } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';

const LIST_PANE = { twoPane: true, side: 'list' };
const HAIRLINE = 0.5;

function isRowSelected(item, kind, id) {
  if (!id) return false;
  if (item.kind === 'workgroup') return kind === 'wg' && item.id === id;
  return kind !== 'wg' && item.id === id;
}

export function SidebarPane() {
  const { colors } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const canAdmin = useCanAdminEarly();
  const { endpoint, probeState } = useEndpoint();
  const { items, loading, refresh } = useInbox();
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

  const selection = sidebarSelection(pathname);
  const selectedKind = selection?.kind ?? null;
  const selectedId = selection?.id ?? null;

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

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);

  useEffect(() => {
    refresh();
  }, [pathname, refresh]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });
    return () => sub?.remove?.();
  }, [refresh]);

  const debouncedRefresh = useDebouncedCallback(refresh, 800);
  useEventEffect(
    [
      'session_changed',
      'wg.post',
      'wg.done',
      'schedule.done',
      'schedule.failed',
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
      const verb = openVerb({ twoPane: true, pathname });
      router[verb](path);
    },
    [router, pathname],
  );

  const togglePin = useCallback(
    (item) => {
      if (item.kind === 'profile') pins.toggleProfile(item.name);
      else pins.toggleWorkgroup(item.profile, item.id);
    },
    [pins],
  );

  const handleLongPress = useCallback((item) => setCtxTarget(item), []);

  const openSettings = useCallback(() => {
    setSheet(null);
    router[openVerb({ twoPane: true, pathname })](SETTINGS_PATH);
  }, [router, pathname]);

  const openNotifications = useCallback(() => {
    setSheet(null);
    router[openVerb({ twoPane: true, pathname })](OUTPUTS_PATH);
  }, [router, pathname]);

  const renderRow = useCallback(
    ({ item }) => (
      <InboxRow
        item={item}
        selected={isRowSelected(item, selectedKind, selectedId)}
        showState
        onPress={openItem}
        onLongPress={handleLongPress}
      />
    ),
    [selectedKind, selectedId, openItem, handleLongPress],
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
    <PaneContext.Provider value={LIST_PANE}>
      <SafeAreaView
        edges={['top', 'left', 'bottom']}
        style={{
          width: SIDEBAR_W,
          flexShrink: 0,
          backgroundColor: colors.bgSide,
          borderRightWidth: HAIRLINE,
          borderRightColor: colors.line,
        }}
      >
        <ConnHeader
          name={endpoint?.name ?? 'No daemon'}
          host={endpointHost(endpoint) || 'not paired'}
          status={daemonStatus}
          searchOpen={searchOpen}
          onToggleSearch={toggleSearch}
          onConnPress={() => setSheet('conn')}
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
          device="tablet"
          gutter={space.s5}
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
    </PaneContext.Provider>
  );
}
