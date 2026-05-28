import { useLocalSearchParams, useRouter } from 'expo-router';
import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../src/theme/tokens';

import { Dot } from '../../src/components/Dot';
import { useToast } from '../../src/components/Toast';
import { WorkgroupMessage } from '../../src/features/chat/Bubble';
import { ChatHeader } from '../../src/features/chat/ChatHeader';
import { useCanAdminEarly } from '../../src/hooks/useActiveRole';
import { ChatSkeleton } from '../../src/features/chat/ChatSkeleton';
import { Composer } from '../../src/features/chat/Composer';
import { MarkerCard } from '../../src/features/chat/MarkerCard';
import { MessageActionsSheet } from '../../src/features/chat/MessageActionsSheet';
import { buildTasks, classifyMessage } from '../../src/features/chat/parseMarkers';
import { TasksSheet } from '../../src/features/sheets/TasksSheet';
import {
  useProfileSummaries,
  useWorkgroupMembers,
  useWorkgroupTranscript,
  useWorkgroups,
} from '../../src/hooks/useDaemonData';
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
  error: { paddingHorizontal: space.s7, marginTop: space.s1 },
  rowPad: { paddingTop: space.s6 },
  emptyHero: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyText: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s9 },
  pausedBanner: {
    paddingHorizontal: space.s7,
    paddingVertical: space.s4,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
  },
});

const WgItem = memo(function WgItem({ m, hubPubkey, ownPubkey, workingStale, accent, accentFor, setActionTarget, colors, fonts, fontSizes }) {
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
        title={c.task?.title || ''}
        speakerName={speakerName}
        isFromHub={isFromHub}
        seq={m.seq}
        cost={m.cost}
      />
    );
  }
  if (c.variant === 'working' && isStaleWorking) {
    return (
      <WorkgroupMessage
        body={c.text || ''}
        speakerName={speakerName}
        speakerAccent={speakerAccent}
        isFromHub={isFromHub}
        seq={m.seq}
        cost={m.cost}
        onLongPress={() => setActionTarget(makeTarget())}
      />
    );
  }
  if (c.variant === 'working' || c.variant === 'done' || c.variant === 'skip') {
    return (
      <MarkerCard
        variant={c.variant}
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
  { messages, hubPubkey, ownPubkey, workingStale, accent, accentFor, setActionTarget, hubLabel, colors, fonts, fontSizes, loading },
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
        />
      </View>
    ),
    [hubPubkey, ownPubkey, workingStale, accent, accentFor, setActionTarget, colors, fonts, fontSizes],
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
      <Dot color={dotColor} size={8} />
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
  useEventEffect(['wg.post', 'wg.done', 'workgroup_members'], (ev) => {
    if (ev.data?.wg_id !== id) return;
    transcript.refresh();
    setOptimistic([]);
  });

  const workingStale = useMemo(() => {
    const stale = new Set();
    if (!messages.length) return stale;
    const seenAuthor = new Set();
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (classifyMessage(m.body).variant === 'working') {
        if (seenAuthor.has(m.from_pubkey)) stale.add(m.seq);
      }
      seenAuthor.add(m.from_pubkey);
    }
    return stale;
  }, [messages]);

  const tasks = useMemo(() => buildTasks(messages), [messages]);

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

  const meta = `hub @${wg.hub_id} · ${members.length || wg.members?.length || 0} members${paused ? ' · paused' : ''}`;

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
        right={tasks.length ? <TasksHeaderButton tasks={tasks} accent={accent} onPress={() => setTasksOpen(true)} /> : null}
      />
      {paused ? (
        <View style={[WG_STYLES.pausedBanner, { backgroundColor: `${colors.warning}22` }]}>
          <Dot color={colors.warning} size={8} />
          <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink2 }}>
            This workgroup is paused. New messages won't fire.
          </Text>
        </View>
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
