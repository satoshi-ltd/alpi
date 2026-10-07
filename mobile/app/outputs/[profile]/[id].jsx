import * as Clipboard from 'expo-clipboard';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { mixHex } from '../../../../common/color.mjs';
import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';
import { headlineParts } from '../../../../common/notificationHeadline.mjs';
import { notificationKey } from '../../../../common/notificationTriage.mjs';
import { ActionSheet } from '../../../src/components/ActionSheet';
import { Button } from '../../../src/components/Button';
import { Fold } from '../../../src/components/Fold';
import { Icon } from '../../../src/components/Icon';
import { ErrorCard, NotificationBody } from '../../../src/components/NotificationBody';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { useToast } from '../../../src/components/Toast';
import { isForeignConnection } from '../../../src/features/aln/deeplink';
import { SeverityTag } from '../../../src/features/notifications/SeverityTag';
import { useIsAdmin } from '../../../src/hooks/useActiveRole';
import { isMissingVerb } from '../../../src/hooks/useActivity';
import { useBack } from '../../../src/hooks/useBack';
import { useProfileSummaries } from '../../../src/hooks/useDaemonData';
import { unreadMissingKey, useNotificationActions, useOutput } from '../../../src/hooks/useOutputs';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { freeze, noteUnreadMissing, trailPosition, UNDO_MS, useNotificationStore } from '../../../src/lib/notificationStore';
import { clip, fmtRelative, openChatTarget, replyDraft } from '../../../src/lib/outputsFormat';
import { useTheme } from '../../../src/theme/ThemeContext';
import { mobile, radii, space } from '../../../src/theme/tokens';
import { ReaderSkeleton } from '../../../src/components/ReaderSkeleton';


function IconButton({ name, label, onPress }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: mobile.iconBtn,
        height: mobile.iconBtn,
        borderRadius: radii.xs,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      <Icon name={name} size="lg" color={colors.ink2} />
    </Pressable>
  );
}


export default function OutputDetailScreen() {
  const { profile, id, connectionId } = useLocalSearchParams();
  return <NotificationPage key={`${connectionId ?? ''}:${profile}:${id}`} profile={profile} id={id} connectionId={connectionId} />;
}


function NotificationPage({ profile, id, connectionId }) {
  const { colors, fonts, fontSizes, mode } = useTheme();
  const router = useRouter();
  const goBack = useBack();
  const toast = useToast();
  const { row, loading, error, markRead, markUnread, runJob } = useOutput(profile, id, connectionId);
  const { activeId, connections, setActive } = useEndpoint();
  const isAdmin = useIsAdmin();
  const summaries = useProfileSummaries();
  const actions = useNotificationActions();
  const store = useNotificationStore();
  const [menuOpen, setMenuOpen] = useState(false);

  const autoRead = useRef(false);
  useEffect(() => {
    if (!row || autoRead.current) return;
    autoRead.current = true;
    if (row.status === 'unread') markRead();
  }, [row, markRead]);

  const entry = useMemo(
    () => (store.trail ?? []).find((e) => e.profile === profile && e.id === id && (e.connectionId || '') === (connectionId || '')) ?? null,
    [store.trail, profile, id, connectionId],
  );
  const position = entry ? trailPosition(entry.key, store) : null;

  const summary = useMemo(
    () => (summaries.data?.profiles ?? []).find((p) => p.name === (row?.profile ?? profile)) ?? null,
    [summaries.data, row?.profile, profile],
  );
  const accent = summary?.accent ?? FALLBACK_ACCENT;
  const nameInk = typeof accent === 'string' && accent.startsWith('#') ? mixHex(accent, mode === 'dark' ? 0.78 : 0.62, colors.ink) : colors.ink;
  const connectionName = (connections ?? []).length > 1
    ? (connections ?? []).find((c) => c.id === connectionId)?.name ?? null
    : null;

  const step = async (target) => {
    if (!target) return;
    freeze(target);
    if (target.connectionId && target.connectionId !== activeId) {
      try { await setActive(target.connectionId); } catch { /* */ }
    }
    router.setParams({ profile: target.profile, id: target.id, connectionId: target.connectionId ?? '' });
  };

  const onCopy = async () => {
    if (!row) return;
    try {
      await Clipboard.setStringAsync(String(row.body ?? ''));
      toast({ title: 'Copied' });
    } catch {
      toast({ title: 'Copy failed', kind: 'danger' });
    }
  };

  const onReply = () => {
    if (!row) return;
    router.push({
      pathname: '/chat/[id]',
      params: { id: row.profile, fresh: String(Date.now()), draft: replyDraft(row), ...(connectionId ? { connectionId } : {}) },
    });
  };

  const missingKey = unreadMissingKey(connectionId, activeId);
  const canMarkUnread = !!row && row.status !== 'unread' && !store.unreadMissing.has(missingKey);
  const onMarkUnread = async () => {
    try {
      await markUnread();
      if (entry) freeze({ ...entry, unread: true });
      toast({ title: 'Marked unread' });
    } catch (e) {
      if (isMissingVerb(e)) noteUnreadMissing(missingKey);
      else toast({ message: `Mark unread failed: ${String(e?.message ?? e)}`, kind: 'danger' });
    }
  };

  const onDelete = () => {
    if (!row) return;
    const target = { profile, id, connectionId: connectionId || undefined };
    const next = position?.next ?? null;
    actions.remove(target, { onError: (e) => toast({ message: `Delete failed: ${String(e?.message ?? e)}`, kind: 'danger' }) });
    toast({
      message: `Deleted “${clip(headlineParts(row).title || 'notification', 48)}”`,
      action: 'Undo',
      onAction: () => actions.undoRemove(target),
      duration: UNDO_MS,
    });
    if (next) step(next);
    else goBack();
  };

  const chatTarget = openChatTarget(row, connectionId);
  const failure = row?.type === 'error';
  const jobId = row?.job_id ? String(row.job_id) : null;
  const canJob = !!jobId && isAdmin && !isForeignConnection(activeId, connectionId);

  const [running, setRunning] = useState(false);
  const runningRef = useRef(false);
  const onRunAgain = async () => {
    if (runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    try {
      await runJob(jobId);
      toast({ message: 'Running again', kind: 'success', duration: 2000 });
    } catch (e) {
      toast({ message: `Run failed: ${String(e?.message ?? e)}`, kind: 'danger', duration: 4000 });
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  };

  const onOpenJob = () => router.push({ pathname: '/profile/[id]/schedule', params: { id: row.profile, job: jobId } });
  const jobActions = canJob ? (
    <>
      <Button title="Run again" variant="primary" size="sm" loading={running} onPress={onRunAgain} />
      <Button title="Open job" variant="secondary" size="sm" onPress={onOpenJob} />
    </>
  ) : null;

  const title = (row?.title || '').trim();
  const menu = [
    { id: 'copy', label: 'Copy', onPress: onCopy },
    ...(chatTarget ? [{ id: 'chat', label: 'Open chat', onPress: () => router.push(chatTarget) }] : []),
  ];

  const nav = (
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      {position ? (
        <>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, marginRight: space.s2 }}>
            {`${position.index + 1} of ${position.total}`}
          </Text>
          {position.prev ? <IconButton name="chevron-up" label="Previous notification" onPress={() => step(position.prev)} /> : null}
          {position.next ? <IconButton name="chevron-down" label="Next notification" onPress={() => step(position.next)} /> : null}
        </>
      ) : null}
      {row ? <IconButton name="ellipsis" label="More" onPress={() => setMenuOpen(true)} /> : null}
    </View>
  );

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="" onBack={goBack} right={nav} />

      {loading && !row ? (
        <ReaderSkeleton label="Loading the output" />
      ) : error || !row ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10, gap: space.s2 }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink2 }}>
            Notification not found
          </Text>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3, textAlign: 'center' }}>
            It may have aged out of the 500-row cap on this profile.
          </Text>
        </View>
      ) : (
        <>
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: space.s7, gap: space.s5, paddingBottom: space.s10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, flexWrap: 'wrap' }}>
              <Fold fold={summary?.fold} color={accent} size={20} />
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: nameInk }}>
                {row.profile}
              </Text>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
                {[connectionName, `${fmtRelative(row.created_at)} ago`].filter(Boolean).join(' · ')}
              </Text>
              {failure ? null : <SeverityTag row={row} />}
            </View>

            {failure ? (
              <ErrorCard title={title} body={row.body || ''} actions={jobActions} />
            ) : (
              <>
                {title ? (
                  <Text accessibilityRole="header" style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xxl, color: colors.ink }}>
                    {title}
                  </Text>
                ) : null}
                <NotificationBody body={row.body || ''} lead={!title} />
              </>
            )}
          </ScrollView>

          <SafeAreaView edges={['bottom']} style={{ backgroundColor: colors.bgSide, borderTopWidth: 0.5, borderTopColor: colors.line2 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: space.s3, paddingHorizontal: space.s5, paddingVertical: space.s4 }}>
              <Button title="Reply" variant={failure ? 'secondary' : 'primary'} size="lg" onPress={onReply} />
              {canJob && !failure ? <Button title="Open job" variant="secondary" size="lg" onPress={onOpenJob} /> : null}
              <View style={{ flex: 1 }} />
              {canMarkUnread ? <IconButton name="eye" label="Mark unread" onPress={onMarkUnread} /> : null}
              <IconButton name="trash-2" label="Delete" onPress={onDelete} />
            </View>
          </SafeAreaView>
        </>
      )}

      <ActionSheet open={menuOpen} onClose={() => setMenuOpen(false)} title={title || 'Notification'} actions={menu} />
    </SafeAreaView>
  );
}
