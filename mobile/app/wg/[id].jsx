import { useLocalSearchParams, useRouter } from 'expo-router';
import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { KeyboardPane } from '../../src/components/KeyboardPane';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space } from '../../src/theme/tokens';

import { ActionSheet } from '../../src/components/ActionSheet';
import { Banner } from '../../src/components/Banner';
import { DaemonBanner, isDaemonDown } from '../../src/components/DaemonBanner';
import { Diamond } from '../../src/components/Diamond';
import { Dot } from '../../src/components/Dot';
import { Meter } from '../../src/components/Meter';
import { useToast } from '../../src/components/Toast';
import { WorkgroupMessage } from '../../src/features/chat/Bubble';
import { ChatHeader, headerMenuActions } from '../../src/features/chat/ChatHeader';
import { SoundWave } from '../../src/features/chat/SoundWave';
import { useBack } from '../../src/hooks/useBack';
import { enqueueReadAloud } from '../../src/lib/readAloud';
import { useCanAdminEarly } from '../../src/hooks/useActiveRole';
import { ChatSkeleton } from '../../src/features/chat/ChatSkeleton';
import { Composer } from '../../src/features/chat/Composer';
import { EmptyThread } from '../../src/features/chat/EmptyThread';
import { MarkerCard } from '../../src/features/chat/MarkerCard';
import { MessageActionsSheet } from '../../src/features/chat/MessageActionsSheet';
import { postsOf, unlandedPosts } from '../../src/features/chat/optimisticPosts';
import { buildTasks, classifyMessage } from '../../src/features/chat/parseMarkers';
import { PipelineStrip } from '../../src/features/chat/PipelineStrip';
import { TasksSheet } from '../../src/features/sheets/TasksSheet';
import {
  useProfileSummaries,
  useWorkgroupMembers,
  useWorkgroupTasks,
  useWorkgroupTranscript,
  useWorkgroups,
} from '../../src/hooks/useDaemonData';
import { useDebouncedCallback } from '../../src/hooks/useDebouncedCallback';
import { useEventEffect } from '../../src/hooks/useEvents';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { isForeignConnection } from '../../src/features/aln/deeplink';
import { CONTENT_MAX_W, PANE_PAD_X } from '../../src/lib/panes';
import { markWorkgroupRead } from '../../src/lib/readState';
import { usePane } from '../../src/nav/PaneContext';
import { resolveMembers } from '../../src/lib/workgroupMembers';
import { accentForProfile } from '../../src/theme/accents';
import { useTheme } from '../../src/theme/ThemeContext';

const INITIAL_PAGE = 30;
const PAGE_STEP = 30;

const WG_STYLES = StyleSheet.create({
  pending: { opacity: 0.6 },
  ready: { opacity: 1 },
  listContent: { paddingTop: space.s5, paddingBottom: space.s5 },
  contentColumn: { alignSelf: 'center', width: '100%', maxWidth: CONTENT_MAX_W },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  error: { paddingHorizontal: PANE_PAD_X, marginTop: space.s1 },
  rowPad: { paddingTop: space.s6 },
  banner: {
    paddingHorizontal: space.s7,
    paddingVertical: space.s4,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
  },
  bannerText: {
    flex: 1,
  },
});

function PaneColumn({ children }) {
  const { twoPane } = usePane();
  return twoPane ? <View style={WG_STYLES.contentColumn}>{children}</View> : children;
}

const WgItem = memo(function WgItem({ m, hubPubkey, ownPubkey, workingStale, accent, accentFor, setActionTarget, colors, fonts, fontSizes, imageProfile }) {
  const speakerName = m.from?.startsWith('@') ? m.from.slice(1) : m.from || '';
  const speakerAccent = accentFor(speakerName, accent);
  const isFromHub = hubPubkey != null && m.from_pubkey === hubPubkey;
  const isOwn = ownPubkey != null && m.from_pubkey === ownPubkey;
  const c = classifyMessage(m.body);
  const isStaleWorking = c.variant === 'working' && workingStale.has(m.seq);
  const makeTarget = () => (
    isOwn ? { kind: 'user', text: m.body } : { kind: 'agent', text: m.body }
  );

  if (c.variant === 'task') {
    return (
      <MarkerCard
        variant="task"
        side={isFromHub ? 'right' : 'left'}
        hubColor={speakerAccent}
        speakerName={speakerName}
        isFromHub={isFromHub}
        seq={m.seq}
        cost={m.cost}
      >
        {c.task?.content || ''}
      </MarkerCard>
    );
  }
  if (c.variant === 'working' || c.variant === 'done' || c.variant === 'skip') {
    return (
      <MarkerCard
        variant={c.variant}
        label={isStaleWorking ? 'WORK' : undefined}
        stale={isStaleWorking}
        side={isFromHub ? 'right' : 'left'}
        hubColor={speakerAccent}
        speakerName={speakerName}
        isFromHub={isFromHub}
        seq={m.seq}
        cost={m.cost}
      >
        {c.text}
      </MarkerCard>
    );
  }
  return (
    <View style={m.pending ? WG_STYLES.pending : WG_STYLES.ready}>
      <WorkgroupMessage
        body={m.body}
        speakerName={speakerName}
        speakerAccent={speakerAccent}
        isFromHub={isFromHub}
        seq={m.seq > 0 ? m.seq : null}
        cost={m.cost}
        profile={imageProfile}
        onLongPress={() => setActionTarget(makeTarget())}
      />
      {m.error ? (
        <Text style={[WG_STYLES.error, { color: colors.danger, fontFamily: fonts.mono, fontSize: fontSizes.xs }]}>
          {m.error}
        </Text>
      ) : null}
    </View>
  );
});

const WgList = forwardRef(function WgList(
  { messages, hubPubkey, ownPubkey, workingStale, accent, accentFor, setActionTarget, hubLabel, colors, fonts, fontSizes, hydrating, imageProfile },
  ref,
) {
  const [pageSize, setPageSize] = useState(INITIAL_PAGE);
  const { twoPane } = usePane();
  const visible = useMemo(() => messages.slice(-pageSize).slice().reverse(), [messages, pageSize]);
  const hasMore = messages.length > pageSize;
  const listRef = useRef(null);

  useImperativeHandle(ref, () => ({
    scrollToSeq: (seq) => {
      if (seq == null) return;
      // Expand page window before scroll — inverted FlatList without getItemLayout throws on offscreen indices.
      const at = messages.findIndex((m) => m.seq === seq);
      if (at < 0) return;
      const idx = messages.length - 1 - at;
      if (idx >= pageSize) {
        setPageSize((n) => Math.max(n, idx + 5));
        setTimeout(() => listRef.current?.scrollToIndex?.({ index: idx, animated: false, viewPosition: 0.3 }), 0);
        return;
      }
      listRef.current?.scrollToIndex?.({ index: idx, animated: true, viewPosition: 0.3 });
    },
  }), [messages, pageSize]);

  const renderItem = useCallback(
    ({ item }) => (
      <View style={WG_STYLES.rowPad}>
        <WgItem
          m={item}
          hubPubkey={hubPubkey}
          ownPubkey={ownPubkey}
          workingStale={workingStale}
          accent={accent}
          accentFor={accentFor}
          setActionTarget={setActionTarget}
          colors={colors}
          fonts={fonts}
          fontSizes={fontSizes}
          imageProfile={imageProfile}
        />
      </View>
    ),
    [hubPubkey, ownPubkey, workingStale, accent, accentFor, setActionTarget, colors, fonts, fontSizes, imageProfile],
  );

  if (hydrating && messages.length === 0) {
    return <ChatSkeleton kind="workgroup" accent={accent} />;
  }
  if (messages.length === 0) {
    return (
      <EmptyThread
        heading="no posts yet"
        detail={`direct @${hubLabel} to open a #task`}
        accent={accent}
      />
    );
  }

  return (
    <FlatList
      ref={listRef}
      inverted
      data={visible}
      keyExtractor={(m, idx) => String(m.seq ?? `i-${idx}`)}
      renderItem={renderItem}
      contentContainerStyle={twoPane ? [WG_STYLES.listContent, WG_STYLES.contentColumn] : WG_STYLES.listContent}
      onEndReached={hasMore ? () => setPageSize((n) => n + PAGE_STEP) : undefined}
      onEndReachedThreshold={0.5}
      initialNumToRender={12}
      maxToRenderPerBatch={10}
      windowSize={9}
      removeClippedSubviews
      onScrollToIndexFailed={({ index, averageItemLength }) => {
        const offset = (averageItemLength || 80) * index;
        listRef.current?.scrollToOffset?.({ offset, animated: false });
        setTimeout(() => listRef.current?.scrollToIndex?.({ index, animated: false, viewPosition: 0.3 }), 80);
      }}
      ListFooterComponent={
        hasMore ? (
          <View style={{ padding: space.s5, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} size="small" />
          </View>
        ) : null
      }
    />
  );
});

function TasksHeaderButton({ tasks, accent, onPress }) {
  const { colors, fonts, fontSizes } = useTheme();
  const closed = tasks.filter((t) => t.status === 'done' || t.status === 'skip').length;
  const total = tasks.length;
  const last = tasks[tasks.length - 1];
  const dotColor =
    last?.status === 'done' ? colors.success
    : last?.status === 'skip' ? colors.warning
    : last?.status === 'working' ? accent
    : colors.ink3;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        paddingHorizontal: space.s4,
        height: 30,
        backgroundColor: pressed ? colors.selected : colors.bgInput,
        borderRadius: radii.lg,
      })}
    >
      <Dot color={dotColor} pulse={last?.status === 'working'} />
      <Text style={{ fontFamily: fonts.monoSemibold, fontSize: fontSizes.xs, color: colors.ink }}>
        {closed}/{total}
      </Text>
    </Pressable>
  );
}

export default function WorkgroupChat() {
  const { id, connectionId } = useLocalSearchParams();
  const goBack = useBack();
  const { colors, fonts } = useTheme();
  const { activeId } = useEndpoint();
  if (isForeignConnection(activeId, connectionId)) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="workgroup" accent={colors.ink3} title={`#${id}`} meta="other connection" onBack={goBack} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10 }}>
          <Text style={{ fontFamily: fonts.sans.regular, color: colors.ink3, textAlign: 'center' }}>
            This notification came from a connection that isn't active. Switch to it to open this workgroup.
          </Text>
        </View>
      </SafeAreaView>
    );
  }
  return <WorkgroupChatInner key={`${activeId ?? ''}:${id}`} />;
}

function WorkgroupChatInner() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors, fonts, fontSizes } = useTheme();
  const canAdmin = useCanAdminEarly();
  const { endpoint, call, probeState } = useEndpoint();
  const summaries = useProfileSummaries();
  const wgs = useWorkgroups();

  const daemonStatus = endpoint ? probeState?.get(endpoint.id) ?? 'unknown' : 'offline';
  const daemonDown = !!endpoint && isDaemonDown(daemonStatus);

  const wg = useMemo(
    () => wgs.data?.workgroups?.find((w) => w.id === id) ?? null,
    [wgs.data, id],
  );

  const profile = wg?.profile ?? null;
  const transcript = useWorkgroupTranscript(profile, id);
  const taskState = useWorkgroupTasks(profile, id);
  const memberList = useWorkgroupMembers(profile, id);

  // Mark read on entry + each turn — wg.mtime advances with every post.
  useEffect(() => {
    if (!profile || !id || !wg?.mtime) return;
    markWorkgroupRead(endpoint?.id, profile, id, wg.mtime);
  }, [endpoint?.id, profile, id, wg?.mtime]);

  const hub = useMemo(() => {
    if (!wg) return null;
    return summaries.data?.profiles?.find((p) => p.name === wg.hub_id) ?? null;
  }, [wg, summaries.data]);
  const hubPubkey = hub?.pubkey_b64 ?? wg?.hub_pubkey_b64 ?? null;
  const ownPubkey = profile
    ? summaries.data?.profiles?.find((p) => p.name === profile)?.pubkey_b64 ?? `local:${profile}`
    : 'local';

  const persisted = postsOf(transcript.data);
  const members = resolveMembers(memberList.data);

  const toast = useToast();
  const [actionTarget, setActionTarget] = useState(null);
  const [composerSeed, setComposerSeed] = useState(null);
  const [sending, setSending] = useState(false);
  const [optimistic, setOptimistic] = useState([]);

  const messages = useMemo(
    () => [...persisted, ...unlandedPosts(optimistic, transcript.data)],
    [persisted, optimistic, transcript.data],
  );

  const pruneOptimistic = useCallback((fetched) => {
    setOptimistic((cur) => unlandedPosts(cur, fetched));
  }, []);

  // session_changed excluded — fires on every profile chat turn, would cause wasted wg transcript fetch+decrypt over Tailscale.
  // Coalesced: each refresh re-fetches and decrypts the 200-post tail, so post bursts must collapse into one.
  const refreshTranscript = useDebouncedCallback(() => {
    transcript.refresh().then(pruneOptimistic);
    taskState.refresh();
  }, 400);
  useEventEffect(['wg.post', 'wg.done', 'workgroup_members'], (ev) => {
    if (ev.data?.wg_id !== id) return;
    refreshTranscript();
  });

  // A #working is stale once superseded — by a later post from the same author, or by the hub's #done that closes the task. A member #skip is a per-peer pass, not a close, so it never marks others' #working stale. Scope resets when crossing a #task boundary going backwards.
  const workingStale = useMemo(() => {
    const stale = new Set();
    if (!messages.length) return stale;
    let seenAuthor = new Set();
    let taskClosed = false;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      const variant = classifyMessage(m.body).variant;
      const fromHub = hubPubkey == null || m.from_pubkey === hubPubkey;
      if (fromHub && variant === 'done') taskClosed = true;
      if (variant === 'working') {
        if (seenAuthor.has(m.from_pubkey) || taskClosed) stale.add(m.seq);
      }
      if (fromHub && variant === 'task') {
        seenAuthor = new Set();
        taskClosed = false;
      }
      seenAuthor.add(m.from_pubkey);
    }
    return stale;
  }, [messages]);

  const tasks = useMemo(() => buildTasks(messages, hubPubkey), [messages, hubPubkey]);
  const loadedSeqs = useMemo(() => new Set(messages.map((m) => m.seq)), [messages]);
  const pipelineRun = taskState.data?.pipeline_run ?? null;
  const blocked = taskState.data?.blocked ?? null;

  const autoRead = !!wg?.auto_read;
  const voiceMap = useMemo(() => {
    const out = {};
    for (const m of members) if (m.pubkey && m.voice) out[m.pubkey] = m.voice;
    return out;
  }, [members]);
  const lastReadSeqRef = useRef(-1);
  const armedWgRef = useRef(null);
  // baseline on the first LOADED transcript so existing history is never auto-read
  useEffect(() => {
    if (!transcript.data) return;
    const maxSeq = messages.reduce((a, m) => Math.max(a, m.seq ?? -1), -1);
    if (armedWgRef.current !== id) {
      armedWgRef.current = id;
      lastReadSeqRef.current = maxSeq;
      return;
    }
    if (!autoRead) {
      lastReadSeqRef.current = maxSeq;
      return;
    }
    const fresh = messages
      .filter((m) => (m.seq ?? -1) > lastReadSeqRef.current && m.from_pubkey !== ownPubkey && m.body)
      .sort((a, b) => a.seq - b.seq);
    if (fresh.length) {
      lastReadSeqRef.current = maxSeq;
      for (const m of fresh) {
        const speakerName = m.from?.startsWith('@') ? m.from.slice(1) : m.from || '';
        const speakerAccent = summaries.data?.profiles?.find((x) => x.name === speakerName)?.accent ?? null;
        enqueueReadAloud({
          call,
          key: `wg:${id}:${m.seq}`,
          voiceId: voiceMap[m.from_pubkey] || 'en-US-AriaNeural',
          text: m.body,
          accent: speakerAccent,
          // scripting resolves a LOCAL profile home on the daemon — speaker names can be remote peers or collide
          profile: profile || null,
        });
      }
    }
  }, [messages, autoRead, id, ownPubkey, voiceMap, call, transcript.data, summaries.data, profile]);
  const blockedReason = useMemo(() => {
    if (!blocked) return '';
    const slug = blocked.slug || '';
    return (blocked.reason || '')
      .replace(/^\s*blocked\b/i, '')
      .replace(new RegExp(`^\\s*${slug}\\b`, 'i'), '')
      .replace(/^[\s·:—-]+/, '')
      .trim();
  }, [blocked]);

  // Workgroups borrow hub profile's accent — daemon shape has no wg.accent.
  const accent = hub?.accent ?? accentForProfile(wg?.hub_id) ?? colors.ink3;
  const paused = wg?.paused;
  const [tasksOpen, setTasksOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const listApiRef = useRef(null);

  const accentFor = useCallback(
    (name, fallback) => {
      const p = summaries.data?.profiles?.find((x) => x.name === name);
      return p?.accent ?? fallback;
    },
    [summaries.data],
  );

  const sendMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || sending || paused || daemonDown) return;
    const tempSeq = -Date.now();
    const optimisticMsg = {
      seq: tempSeq,
      from: `@${profile}`,
      from_pubkey: ownPubkey,
      body: trimmed,
      pending: true,
    };
    setOptimistic((cur) => [...cur, optimisticMsg]);
    setSending(true);
    try {
      await call('host.workgroup.post', { profile, wg_id: id, text: trimmed });
      const fetched = await transcript.refresh();
      taskState.refresh();
      pruneOptimistic(fetched);
    } catch (e) {
      setOptimistic((cur) =>
        cur.map((m) => (m.seq === tempSeq ? { ...m, pending: false, error: String(e) } : m)),
      );
    } finally {
      setSending(false);
    }
  };

  if (!endpoint) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="workgroup" accent={colors.ink3} title={`#${id}`} meta="not paired" onBack={goBack} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ fontFamily: fonts.sans.regular, color: colors.ink3 }}>Pair this phone to a daemon first.</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (wgs.loading && !wg) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="workgroup" accent={colors.ink3} title={`#${id}`} meta="loading…" onBack={goBack} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      </SafeAreaView>
    );
  }

  if (!wg) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="workgroup" accent={colors.ink3} title={`#${id}`} meta="workgroup · not found" onBack={goBack} />
      </SafeAreaView>
    );
  }

  const memberCount = members.length || wg.members || 0;
  const budgetCap = Number(wg.budget_usd ?? 0);
  const budgetUsed = Number(wg.spent_usd ?? 0);
  const metaTextStyle = {
    fontFamily: fonts.mono,
    fontSize: fontSizes.xs,
    color: colors.ink3,
  };
  const meta = (
    <>
      <Text style={metaTextStyle}>hub</Text>
      <Diamond color={accent} />
      <Text style={metaTextStyle}>
        {`@${wg.hub_id} · ${memberCount} members`}
      </Text>
      {budgetCap > 0 ? (
        <Meter
          label="Workgroup budget"
          value={`$${budgetUsed.toFixed(2)}`}
          tail={`/$${budgetCap.toFixed(2)}`}
          pct={budgetUsed / budgetCap}
          color={accent}
        />
      ) : null}
    </>
  );

  const menuActions = headerMenuActions({
    noun: 'workgroup',
    paused: !!paused,
    autoRead,
    onOpenSettings: canAdmin ? () => router.push(`/wg/${wg.id}/settings`) : null,
    onTogglePause: canAdmin && wg.is_hub
      ? () =>
          call('host.workgroup.action', { profile: wg.profile, wg_id: wg.id, action: paused ? 'resume' : 'pause' })
            .then(() => wgs.refresh())
            .catch((e) => toast({ title: paused ? 'resume failed' : 'pause failed', message: String(e) }))
      : null,
    onToggleAutoRead: canAdmin
      ? () =>
          call('host.workgroup.update', { profile: wg.profile, wg_id: wg.id, auto_read: !autoRead })
            .then(() => wgs.refresh())
            .catch((e) => toast({ title: 'auto-read failed', message: String(e) }))
      : null,
    onRefresh: () => {
      transcript.refresh();
      taskState.refresh();
    },
  });

  const mentionSource = (needle) => {
    const n = needle.toLowerCase();
    return members
      .map((m) => (typeof m === 'string' ? m : m.name ?? m.handle))
      .filter((m) => m && (!n || m.toLowerCase().includes(n)))
      .map((m) => ({ id: m, role: m === wg.hub_id ? 'hub' : 'member' }));
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ChatHeader
        kind="workgroup"
        accent={accent}
        title={wg.name || wg.id}
        meta={meta}
        onBack={goBack}
        onMore={() => setMenuOpen(true)}
        right={(
          <View style={WG_STYLES.headerRight}>
            <SoundWave accent={accent} />
            {tasks.length ? <TasksHeaderButton tasks={tasks} accent={accent} onPress={() => setTasksOpen(true)} /> : null}
          </View>
        )}
      />
      <DaemonBanner status={daemonStatus} paired={!!endpoint} onRetry={() => transcript.refresh()} />
      {taskState.error ? (
        <Banner kind="warning">
          <Text style={{ fontFamily: fonts.sans.semibold ?? fonts.sans.medium, color: colors.ink }}>
            Workgroup state unavailable.
          </Text>
          {' '}The daemon did not answer, so the phase strip and the blocked banner may be out of date.
        </Banner>
      ) : null}
      {blocked ? (
        <View style={[WG_STYLES.banner, { backgroundColor: `${colors.danger}1f` }]}>
          <Dot color={colors.danger} pulse />
          <Text numberOfLines={2} style={[WG_STYLES.bannerText, { fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * 1.4, color: colors.ink2 }]}>
            <Text style={{ fontFamily: fonts.sans.semibold ?? fonts.sans.medium, color: colors.ink }}>Blocked at #{blocked.slug}.</Text>
            {blockedReason ? ` ${blockedReason}` : ''}
          </Text>
        </View>
      ) : null}
      {paused ? (
        <View style={[WG_STYLES.banner, { backgroundColor: `${colors.warning}22` }]}>
          <Dot color={colors.warning} pulse />
          <Text numberOfLines={2} style={[WG_STYLES.bannerText, { fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * 1.4, color: colors.ink2 }]}>
            <Text style={{ fontFamily: fonts.sans.semibold ?? fonts.sans.medium, color: colors.ink }}>This workgroup is paused.</Text>
            {' '}New messages won't fire. Resume from the header.
          </Text>
        </View>
      ) : null}
      <PipelineStrip
        run={pipelineRun}
        accent={accent}
        loadedSeqs={loadedSeqs}
        onPickSeq={(seq) => listApiRef.current?.scrollToSeq?.(seq)}
      />
      <KeyboardPane>
        <WgList
          ref={listApiRef}
          messages={messages}
          hubPubkey={hubPubkey}
          ownPubkey={ownPubkey}
          workingStale={workingStale}
          accent={accent}
          accentFor={accentFor}
          setActionTarget={setActionTarget}
          hubLabel={wg.hub_id}
          colors={colors}
          fonts={fonts}
          fontSizes={fontSizes}
          hydrating={transcript.loading && !transcript.data}
          imageProfile={profile}
        />
        <PaneColumn>
          <Composer
            placeholder={`Direct @${wg.hub_id} — your input becomes a #task`}
            accent={accent}
            disabled={!!paused || daemonDown}
            onSend={sendMessage}
            mentionSource={mentionSource}
            seedText={composerSeed?.text}
            seedKey={composerSeed?.key}
          />
        </PaneColumn>
      </KeyboardPane>
      <ActionSheet
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        title={`#${wg.name || wg.id}`}
        subtitle="WORKGROUP"
        actions={menuActions}
      />
      <MessageActionsSheet
        target={actionTarget}
        onClose={() => setActionTarget(null)}
        onEdit={(t) => {
          setComposerSeed({ text: t.text ?? '', key: Date.now() });
          setActionTarget(null);
        }}
        onRetry={(t) => {
          setActionTarget(null);
          if (t?.text) sendMessage(t.text);
        }}
      />
      <TasksSheet
        open={tasksOpen}
        onClose={() => setTasksOpen(false)}
        tasks={tasks}
        workgroupId={wg.name || wg.id}
        accent={accent}
        onPick={(seq) => listApiRef.current?.scrollToSeq?.(seq)}
      />
    </SafeAreaView>
  );
}
