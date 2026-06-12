import { useLocalSearchParams, useRouter } from 'expo-router';
import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../src/theme/tokens';

import { Diamond } from '../../src/components/Diamond';
import { Dot } from '../../src/components/Dot';
import { useToast } from '../../src/components/Toast';
import { WorkgroupMessage } from '../../src/features/chat/Bubble';
import { ChatHeader } from '../../src/features/chat/ChatHeader';
import { SoundWave } from '../../src/features/chat/SoundWave';
import { enqueueReadAloud } from '../../src/lib/readAloud';
import { useCanAdminEarly } from '../../src/hooks/useActiveRole';
import { ChatSkeleton } from '../../src/features/chat/ChatSkeleton';
import { Composer } from '../../src/features/chat/Composer';
import { MarkerCard } from '../../src/features/chat/MarkerCard';
import { MessageActionsSheet } from '../../src/features/chat/MessageActionsSheet';
import { buildTasks, classifyMessage, findBlocked, pipelineState } from '../../src/features/chat/parseMarkers';
import { Icon } from '../../src/components/Icon';
import { TasksSheet } from '../../src/features/sheets/TasksSheet';
import {
  useProfileSummaries,
  useWorkgroupMembers,
  useWorkgroupTranscript,
  useWorkgroups,
} from '../../src/hooks/useDaemonData';
import { useDebouncedCallback } from '../../src/hooks/useDebouncedCallback';
import { useEventEffect } from '../../src/hooks/useEvents';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { markWorkgroupRead } from '../../src/lib/readState';
import { accentForProfile } from '../../src/theme/accents';
import { useTheme } from '../../src/theme/ThemeContext';

const INITIAL_PAGE = 30;
const PAGE_STEP = 30;

const WG_STYLES = StyleSheet.create({
  pending: { opacity: 0.6 },
  ready: { opacity: 1 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  error: { paddingHorizontal: space.s7, marginTop: space.s1 },
  rowPad: { paddingTop: space.s6 },
  emptyHero: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyText: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s9 },
  banner: {
    paddingHorizontal: space.s7,
    paddingVertical: space.s4,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
  },
  bannerText: {
    flex: 1,
    fontSize: fontSizes.sm,
    lineHeight: fontSizes.sm * 1.4,
  },
  pipeline: {
    flexGrow: 0,
    flexShrink: 0,
  },
  pipelineContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
    paddingHorizontal: space.s7,
    paddingVertical: space.s4,
  },
  pipelineLabel: {
    fontSize: fontSizes.xs,
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  pipelineSep: {
    fontSize: fontSizes.sm,
    marginRight: space.s3,
  },
  phaseWrap: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  phase: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s1,
  },
});

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
  { messages, hubPubkey, ownPubkey, workingStale, accent, accentFor, setActionTarget, hubLabel, colors, fonts, fontSizes, loading, imageProfile },
  ref,
) {
  const [pageSize, setPageSize] = useState(INITIAL_PAGE);
  const visible = useMemo(() => messages.slice(-pageSize).slice().reverse(), [messages, pageSize]);
  const hasMore = messages.length > pageSize;
  const listRef = useRef(null);

  useImperativeHandle(ref, () => ({
    scrollToSeq: (seq) => {
      if (seq == null) return;
      // Expand page window before scroll — inverted FlatList without getItemLayout throws on offscreen indices.
      const idx = messages.length - 1 - messages.findIndex((m) => m.seq === seq);
      if (idx < 0) return;
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

  if (loading && messages.length === 0) {
    return <ChatSkeleton kind="workgroup" accent={accent} />;
  }
  if (!loading && messages.length === 0) {
    return (
      <View style={WG_STYLES.emptyText}>
        <Text style={{ color: colors.ink3, fontFamily: fonts.sans.regular, fontSize: fontSizes.md }}>
          No messages yet. Direct @{hubLabel} to open a #task.
        </Text>
      </View>
    );
  }

  return (
    <FlatList
      ref={listRef}
      inverted
      data={visible}
      keyExtractor={(m, idx) => String(m.seq ?? `i-${idx}`)}
      renderItem={renderItem}
      contentContainerStyle={{ paddingTop: space.s5, paddingBottom: space.s5 }}
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

function PipelinePhase({ phase, colors, fonts, accent, onPress }) {
  const { slug, state } = phase;
  const icon =
    state === 'completed' ? <Icon name="check" size={12} color={colors.success} />
    : state === 'blocked' ? <Icon name="ban" size={12} color={colors.danger} />
    : state === 'current' ? <Dot color={accent ?? colors.ink} pulse />
    : null;
  const textColor =
    state === 'blocked' ? colors.danger
    : state === 'current' ? accent
    : state === 'pending' ? colors.ink3
    : colors.ink2;
  const Wrapper = onPress ? Pressable : View;
  return (
    <Wrapper
      onPress={onPress}
      style={[
        WG_STYLES.phase,
        state === 'blocked' && {
          backgroundColor: `${colors.danger}17`,
          borderRadius: 999,
          paddingHorizontal: space.s3,
          paddingVertical: 2,
        },
      ]}
    >
      {icon}
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: textColor }}>#{slug}</Text>
    </Wrapper>
  );
}

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
        borderRadius: radii.md,
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
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const canAdmin = useCanAdminEarly();
  const { endpoint, call } = useEndpoint();
  const summaries = useProfileSummaries();
  const wgs = useWorkgroups();

  const wg = useMemo(
    () => wgs.data?.workgroups?.find((w) => w.id === id) ?? null,
    [wgs.data, id],
  );

  const profile = wg?.profile ?? null;
  const transcript = useWorkgroupTranscript(profile, id);
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

  const persistedRaw = transcript.data?.posts ?? transcript.data?.messages ?? [];
  const persisted = Array.isArray(persistedRaw) ? persistedRaw : [];
  const members = memberList.data?.members ?? wg?.members ?? [];

  const toast = useToast();
  const [actionTarget, setActionTarget] = useState(null);
  const [composerSeed, setComposerSeed] = useState(null);
  const [sending, setSending] = useState(false);
  const [optimistic, setOptimistic] = useState([]);

  const persistedBodies = useMemo(() => new Set(persisted.map((m) => `${m.from_pubkey}|${m.body}`)), [persisted]);
  const messages = useMemo(() => {
    const visibleOptimistic = optimistic.filter((m) => !persistedBodies.has(`${m.from_pubkey}|${m.body}`));
    return [...persisted, ...visibleOptimistic];
  }, [persisted, optimistic, persistedBodies]);

  // session_changed excluded — fires on every profile chat turn, would cause wasted wg transcript fetch+decrypt over Tailscale.
  // Coalesced: each refresh re-fetches and decrypts the 200-post tail, so post bursts must collapse into one.
  const refreshTranscript = useDebouncedCallback(() => {
    transcript.refresh();
    setOptimistic([]);
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
  const blocked = useMemo(() => findBlocked(messages, hubPubkey), [messages, hubPubkey]);

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
        });
      }
    }
  }, [messages, autoRead, id, ownPubkey, voiceMap, call, transcript.data, summaries.data]);
  const phases = useMemo(
    () => pipelineState(wg?.pipeline || [], messages, hubPubkey),
    [wg?.pipeline, messages, hubPubkey],
  );
  const activePhase = useMemo(() => {
    if (!phases.length) return 0;
    const b = phases.findIndex((p) => p.state === 'blocked');
    if (b >= 0) return b;
    const c = phases.findIndex((p) => p.state === 'current');
    if (c >= 0) return c;
    let last = 0;
    phases.forEach((p, i) => { if (p.state === 'completed') last = i; });
    return last;
  }, [phases]);
  const pipelineScrollRef = useRef(null);
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
  const listApiRef = useRef(null);

  const sendMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
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
      await transcript.refresh();
      setOptimistic((cur) => cur.filter((m) => m.seq !== tempSeq));
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
        <ChatHeader kind="workgroup" accent={colors.ink3} title={`#${id}`} meta="not paired" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ color: colors.ink3 }}>Pair this phone to a daemon first.</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (wgs.loading && !wg) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="workgroup" accent={colors.ink3} title={`#${id}`} meta="loading…" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      </SafeAreaView>
    );
  }

  if (!wg) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="workgroup" accent={colors.ink3} title={`#${id}`} meta="workgroup · not found" onBack={() => router.back()} />
      </SafeAreaView>
    );
  }

  const memberCount = members.length || wg.members?.length || 0;
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
    </>
  );

  const mentionSource = (needle) => {
    const n = needle.toLowerCase();
    const list = members.length ? members : (wg.members ?? []);
    return list
      .map((m) => (typeof m === 'string' ? m : m.name ?? m.handle))
      .filter((m) => m && (!n || m.toLowerCase().includes(n)))
      .map((m) => ({ id: m, role: m === wg.hub_id ? 'hub' : 'member' }));
  };

  const accentFor = useCallback(
    (name, fallback) => {
      const p = summaries.data?.profiles?.find((x) => x.name === name);
      return p?.accent ?? fallback;
    },
    [summaries.data],
  );

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ChatHeader
        kind="workgroup"
        accent={accent}
        title={wg.name || wg.id}
        meta={meta}
        onBack={() => router.back()}
        onMore={canAdmin ? () => router.push(`/wg/${wg.id}/settings`) : null}
        right={(
          <View style={styles.headerRight}>
            <SoundWave accent={accent} />
            {tasks.length ? <TasksHeaderButton tasks={tasks} accent={accent} onPress={() => setTasksOpen(true)} /> : null}
          </View>
        )}
      />
      {blocked ? (
        <View style={[WG_STYLES.banner, { backgroundColor: `${colors.danger}1f` }]}>
          <Dot color={colors.danger} pulse />
          <Text numberOfLines={2} style={[WG_STYLES.bannerText, { fontFamily: fonts.sans.medium, color: colors.ink2 }]}>
            <Text style={{ fontFamily: fonts.sans.semibold ?? fonts.sans.medium, color: colors.ink }}>Blocked at #{blocked.slug}.</Text>
            {blockedReason ? ` ${blockedReason}` : ''}
          </Text>
        </View>
      ) : null}
      {paused ? (
        <View style={[WG_STYLES.banner, { backgroundColor: `${colors.warning}22` }]}>
          <Dot color={colors.warning} pulse />
          <Text numberOfLines={2} style={[WG_STYLES.bannerText, { fontFamily: fonts.sans.medium, color: colors.ink2 }]}>
            <Text style={{ fontFamily: fonts.sans.semibold ?? fonts.sans.medium, color: colors.ink }}>This workgroup is paused.</Text>
            {' '}New messages won't fire. Resume from the header.
          </Text>
        </View>
      ) : null}
      {phases.length ? (
        <ScrollView
          ref={pipelineScrollRef}
          horizontal
          showsHorizontalScrollIndicator={false}
          style={WG_STYLES.pipeline}
          contentContainerStyle={WG_STYLES.pipelineContent}
        >
          <Text style={[WG_STYLES.pipelineLabel, { fontFamily: fonts.mono, color: colors.ink3 }]}>
            PIPELINE
          </Text>
          {phases.map((p, i) => (
            <View
              key={p.slug}
              style={WG_STYLES.phaseWrap}
              onLayout={(e) => {
                if (i === activePhase) {
                  const x = Math.max(0, e.nativeEvent.layout.x - 24);
                  pipelineScrollRef.current?.scrollTo?.({ x, animated: false });
                }
              }}
            >
              {i > 0 ? <Text style={[WG_STYLES.pipelineSep, { color: colors.ink4 ?? colors.ink3 }]}>›</Text> : null}
              <PipelinePhase
                phase={p}
                colors={colors}
                fonts={fonts}
                accent={accent}
                onPress={p.seq != null ? () => listApiRef.current?.scrollToSeq?.(p.seq) : undefined}
              />
            </View>
          ))}
        </ScrollView>
      ) : null}
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
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
          loading={transcript.loading}
          imageProfile={profile}
        />
        <Composer
          placeholder={`Direct @${wg.hub_id} — your input becomes a #task`}
          accent={accent}
          onSend={sendMessage}
          onMicPress={() => toast({ title: 'Voice messages coming soon', kind: 'info', duration: 1800 })}
          onMicLongPress={() => toast({ title: 'Voice messages coming soon', kind: 'info', duration: 1800 })}
          mentionSource={mentionSource}
          seedText={composerSeed?.text}
          seedKey={composerSeed?.key}
        />
      </KeyboardAvoidingView>
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
