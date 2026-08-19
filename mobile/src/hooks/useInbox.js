import { useCallback, useEffect, useMemo, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';
import { profileEmptyState } from '../lib/profileReady';
import { profileLabel } from '../lib/profileLabel';
import { useReadState } from '../lib/readState';
import { accentForProfile } from '../theme/accents';
import { useProfileSummaries, useWorkgroups } from './useDaemonData';
import { useEventEffect } from './useEvents';

const ACTIVITY_EVENTS = ['wg.post', 'wg.done', 'wg.mention'];
const ACTIVITY_TTL_MS = 10000;
const ACTIVITY_SWEEP_MS = 3000;

function sweepActivity(prev, cutoff) {
  const live = Object.entries(prev).filter(([, at]) => at > cutoff);
  return live.length === Object.keys(prev).length ? prev : Object.fromEntries(live);
}

const PREVIEW_NEEDS_PROVIDER = 'needs a provider · tap to set up';
const PREVIEW_NEEDS_MODEL = 'pick a model · tap to set up';
const PREVIEW_NO_HISTORY = 'tap to start a thread';
const PREVIEW_PAUSED = 'paused · resume to chat';
const PREVIEW_WG_NO_POSTS = 'tap to open a #task';
const PREVIEW_WG_PAUSED = 'paused · resume to post';

function previewFromSession(latest) {
  if (!latest) return '';
  // `first_user` is the pre-0.4.49 fallback when only the thread topic was in the summary.
  return String(
    latest.last_assistant
    || latest.last_user
    || latest.first_user
    || latest.title
    || '',
  ).trim();
}

function profilePreview(profile, state) {
  if (state === 'needs-provider') return PREVIEW_NEEDS_PROVIDER;
  if (state === 'needs-model') return PREVIEW_NEEDS_MODEL;
  return (
    previewFromSession(profile.latest_session)
    || (profile.paused ? PREVIEW_PAUSED : PREVIEW_NO_HISTORY)
  );
}

function workgroupPreview(workgroup) {
  return (
    String(workgroup.last_body || workgroup.briefing || '').trim()
    || (workgroup.paused ? PREVIEW_WG_PAUSED : PREVIEW_WG_NO_POSTS)
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
  const [activity, setActivity] = useState({});

  // Keyed by wg_id alone — the event names the emitting profile, which needn't be the deduped row's.
  useEventEffect(ACTIVITY_EVENTS, (ev) => {
    const wgId = ev?.data?.wg_id;
    if (!wgId) return;
    setActivity((prev) => ({ ...prev, [wgId]: Date.now() }));
  });

  useEffect(() => {
    setActivity({});
    const timer = setInterval(
      () => setActivity((prev) => sweepActivity(prev, Date.now() - ACTIVITY_TTL_MS)),
      ACTIVITY_SWEEP_MS,
    );
    return () => clearInterval(timer);
  }, [endpoint?.id]);

  const items = useMemo(() => {
    const profileItems = (profilesQ.data?.profiles ?? []).map((p) => {
      const state = profileEmptyState(p);
      const blocked = state !== 'ready';
      const preview = profilePreview(p, state);
      const sessionTs =
        p.latest_session?.updated_at ?? p.latest_session?.mtime ?? p.latest_session?.started_at ?? 0;
      const unread = !blocked && sessionTs > 0 && checkProfile(p.name, sessionTs);
      return {
        kind: 'profile',
        id: p.name,
        name: p.name,
        label: profileLabel(p.name),
        accent: p.accent ?? accentForProfile(p.name),
        needsProvider: blocked,
        emptyState: state,
        preview,
        unread,
        ts: blocked ? null : fmtRelative(sessionTs),
        sortKey: sessionTs,
        paused: !!p.paused,
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
        preview: workgroupPreview(w),
        unread,
        state: activity[w.id] ? 'working' : undefined,
        ts: fmtRelative(wgTs),
        sortKey: wgTs,
        raw: w,
      };
    });
    return [...profileItems, ...wgItems].sort((a, b) => {
      if (!!a.paused !== !!b.paused) return a.paused ? 1 : -1;
      if (!!a.needsProvider !== !!b.needsProvider) return a.needsProvider ? 1 : -1;
      return b.sortKey - a.sortKey;
    });
  }, [profilesQ.data, wgsQ.data, activity, checkProfile, checkWorkgroup]);

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
