import { useCallback, useMemo } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { profileEmptyState } from '../lib/profileReady';
import { useReadState } from '../lib/readState';
import { accentForProfile } from '../theme/accents';
import { useProfileSummaries, useWorkgroups } from './useDaemonData';

function previewFromSession(latest) {
  if (!latest) return '';
  // `first_user` is the pre-0.4.49 fallback when only the thread topic was in the summary.
  return (
    latest.last_assistant
    || latest.last_user
    || latest.first_user
    || latest.title
    || ''
  );
}

function fmtRelative(sec) {
  if (!sec) return null;
  const now = Date.now() / 1000;
  const diff = Math.max(0, now - sec);
  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.round(diff / 60)}m`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d`;
  return `${Math.round(diff / (86400 * 7))}w`;
}

export function useInbox() {
  const profilesQ = useProfileSummaries();
  const wgsQ = useWorkgroups();
  const { endpoint } = useEndpoint();
  // connId-partitioned so switching paired daemons doesn't bleed unreads.
  const { checkProfile, checkWorkgroup } = useReadState(endpoint?.id);

  const items = useMemo(() => {
    const profileItems = (profilesQ.data?.profiles ?? []).map((p) => {
      const state = profileEmptyState(p);
      const blocked = state !== 'ready';
      const preview =
        state === 'needs-provider'
          ? 'needs a provider · tap to set up'
          : state === 'needs-model'
            ? 'pick a model · tap to set up'
            : previewFromSession(p.latest_session);
      const sessionTs =
        p.latest_session?.updated_at ?? p.latest_session?.mtime ?? p.latest_session?.started_at ?? 0;
      const unread = !blocked && sessionTs > 0 && checkProfile(p.name, sessionTs);
      return {
        kind: 'profile',
        id: p.name,
        name: p.name,
        label: p.name,
        accent: p.accent ?? accentForProfile(p.name),
        needsProvider: blocked,
        emptyState: state,
        preview,
        unread,
        ts: blocked ? null : fmtRelative(sessionTs),
        sortKey: sessionTs,
        raw: p,
      };
    });
    const profileByName = new Map((profilesQ.data?.profiles ?? []).map((p) => [p.name, p]));
    const wgItems = (wgsQ.data?.workgroups ?? []).map((w) => {
      const wgTs = w.mtime ?? 0;
      const unread = !w.paused && wgTs > 0 && checkWorkgroup(w.profile, w.id, wgTs);
      // Workgroups borrow the hub profile's accent — they don't carry their own.
      const hub = profileByName.get(w.hub_id);
      return {
        kind: 'workgroup',
        id: w.id,
        profile: w.profile,
        name: w.name ?? w.id,
        label: w.name ?? w.id,
        accent: hub?.accent ?? accentForProfile(w.hub_id),
        paused: w.paused,
        preview: w.last_body || w.briefing || '',
        unread,
        ts: fmtRelative(wgTs),
        sortKey: wgTs,
        raw: w,
      };
    });
    // Filter sessionless items — reachable via Compose FAB instead.
    const active = [...profileItems, ...wgItems].filter((it) => it.sortKey > 0);
    return active.sort((a, b) => {
      if (!!a.unread !== !!b.unread) return a.unread ? -1 : 1;
      return b.sortKey - a.sortKey;
    });
  }, [profilesQ.data, wgsQ.data, checkProfile, checkWorkgroup]);

  // Stable ref so useFocusEffect(useCallback(refresh, [refresh])) doesn't infinite-loop.
  const refresh = useCallback(
    async () => {
      await Promise.all([profilesQ.refresh(), wgsQ.refresh()]);
    },
    [profilesQ.refresh, wgsQ.refresh],
  );

  return {
    items,
    loading: profilesQ.loading || wgsQ.loading,
    error: profilesQ.error ?? wgsQ.error,
    refresh,
  };
}
