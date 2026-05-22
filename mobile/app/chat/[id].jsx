import { useLocalSearchParams, useRouter } from 'expo-router';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../src/theme/tokens';

import { AlpiMark } from '../../src/components/AlpiMark';
import { Button } from '../../src/components/Button';
import { useToast } from '../../src/components/Toast';
import { ProfileAssistantMessage, ProfileUserMessage } from '../../src/features/chat/Bubble';
import { ChatHeader } from '../../src/features/chat/ChatHeader';
import { Composer } from '../../src/features/chat/Composer';
import { MessageActionsSheet } from '../../src/features/chat/MessageActionsSheet';
import { ChatSkeleton } from '../../src/features/chat/ChatSkeleton';
import { ThinkingDots } from '../../src/features/chat/ThinkingDots';
import { ToolCallGroup, groupConsecutiveTools } from '../../src/features/chat/ToolCallRow';
import { SessionsSheet } from '../../src/features/sheets/SessionsSheet';
import { useChatSend } from '../../src/hooks/useChatSend';
import { useProfileSummaries, useSession, useSessionsList } from '../../src/hooks/useDaemonData';
import { useEventEffect } from '../../src/hooks/useEvents';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { profileEmptyState } from '../../src/lib/profileReady';
import { markProfileRead } from '../../src/lib/readState';
import { useTheme } from '../../src/theme/ThemeContext';

function relativeTime(ms) {
  if (!ms) return '';
  const diff = Date.now() - ms;
  if (diff < 60_000) return 'now';
  if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h`;
  return `${Math.round(diff / 86_400_000)}d`;
}

const INITIAL_PAGE = 30;
const PAGE_STEP = 30;

const TURN_STYLES = StyleSheet.create({
  block: { gap: space.s4, paddingTop: space.s8 },
  tools: { gap: space.s1 },
  thinkingHolder: { alignSelf: 'flex-start' },
  error: { paddingHorizontal: space.s7 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s10, gap: space.s10 },
  emptyTextWrap: { gap: space.s4, alignItems: 'center' },
  emptyHeading: { fontSize: fontSizes.hLg, lineHeight: 26, letterSpacing: -0.018 * 22, textAlign: 'center' },
  emptyModel: { fontSize: fontSizes.sm, textAlign: 'center' },
});

const TurnBlock = memo(function TurnBlock({ turn, accent, colors, fonts, fontSizes, onActionTarget }) {
  const ts = turn.at ? relativeTime(turn.at * 1000) : '';
  return (
    <View style={TURN_STYLES.block}>
      {turn.user ? (
        <ProfileUserMessage
          text={turn.user}
          ts={ts}
          accent={accent}
          onLongPress={() => onActionTarget({ kind: 'user', text: turn.user })}
        />
      ) : null}
      {turn.tools?.length ? (
        <View style={TURN_STYLES.tools}>
          {groupConsecutiveTools(turn.tools).map((g, i) => (
            <ToolCallGroup key={`g-${i}-${g.tools[0].tool_id ?? g.name}`} group={g} accent={accent} />
          ))}
        </View>
      ) : null}
      {turn.assistant ? (
        <ProfileAssistantMessage
          text={turn.assistant}
          onLongPress={() => onActionTarget({ kind: 'agent', text: turn.assistant })}
        />
      ) : turn.pending && !(turn.tools?.length) ? (
        <View style={TURN_STYLES.thinkingHolder}>
          <ThinkingDots color={accent} />
        </View>
      ) : null}
      {turn.error ? (
        <Text style={[TURN_STYLES.error, { color: colors.danger, fontFamily: fonts.mono, fontSize: fontSizes.xs }]}>
          {turn.error}
        </Text>
      ) : null}
    </View>
  );
});

function EmptyThread({ profileName, model, accent, colors, fonts }) {
  return (
    <View style={TURN_STYLES.empty}>
      <AlpiMark size={96} color={accent} />
      <View style={TURN_STYLES.emptyTextWrap}>
        <Text style={[TURN_STYLES.emptyHeading, { fontFamily: fonts.sans.semibold, color: colors.ink }]}>
          start a thread with @{profileName}
        </Text>
        {model ? (
          <Text
            style={[TURN_STYLES.emptyModel, { fontFamily: fonts.monoMedium, color: colors.ink3 }]}
            numberOfLines={1}
          >
            {model}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

function ChatList({ turns, pendingTurn, loading, hydrating, profileName, model, accent, onActionTarget, colors, fonts, fontSizes }) {
  const [pageSize, setPageSize] = useState(INITIAL_PAGE);

  // Drop pendingTurn once daemon persists the same user message → avoids 1-frame duplicate.
  const full = useMemo(() => {
    const out = [...turns];
    if (pendingTurn) {
      const last = turns[turns.length - 1];
      const persisted =
        last &&
        last.user === pendingTurn.user &&
        (last.assistant?.length ?? 0) > 0;
      if (!persisted) out.push(pendingTurn);
    }
    return out;
  }, [turns, pendingTurn]);

  const visible = useMemo(() => full.slice(-pageSize).slice().reverse(), [full, pageSize]);
  const hasMore = full.length > pageSize;

  const renderItem = useCallback(
    ({ item }) => (
      <TurnBlock
        turn={item}
        accent={accent}
        colors={colors}
        fonts={fonts}
        fontSizes={fontSizes}
        onActionTarget={onActionTarget}
      />
    ),
    [accent, colors, fonts, fontSizes, onActionTarget],
  );

  if ((loading || hydrating) && full.length === 0) {
    return <ChatSkeleton kind="profile" accent={accent} />;
  }
  if (full.length === 0) {
    return <EmptyThread profileName={profileName} model={model} accent={accent} colors={colors} fonts={fonts} />;
  }

  return (
    <FlatList
      inverted
      data={visible}
      // Composite key: pending and the matching persisted turn share idx 0 in the inverted visible window → row stays mounted across the done→refresh swap. Adding idx disambiguates same-text repeats (sending "ok" twice no longer collides).
      keyExtractor={(turn, idx) => `${turn.user ?? ''}|${idx}`}
      renderItem={renderItem}
      contentContainerStyle={{ paddingTop: space.s5, paddingBottom: space.s5 }}
      onEndReached={hasMore ? () => setPageSize((n) => n + PAGE_STEP) : undefined}
      onEndReachedThreshold={0.5}
      initialNumToRender={12}
      maxToRenderPerBatch={10}
      windowSize={9}
      removeClippedSubviews
      ListFooterComponent={
        hasMore ? (
          <View style={{ padding: space.s5, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} size="small" />
          </View>
        ) : null
      }
    />
  );
}

function NeedsSetup({ name, accent, state, onSetupProvider, onPickModel }) {
  const { colors, fonts, fontSizes, lineHeights } = useTheme();
  const isModel = state === 'needs-model';
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10, gap: space.s6 }}>
      <AlpiMark size={80} color={accent} />
      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink, marginTop: space.s3 }}>
        @{name} needs {isModel ? 'a model' : 'a provider'}
      </Text>
      <Text
        style={{
          fontFamily: fonts.sans.regular,
          fontSize: fontSizes.md,
          color: colors.ink2,
          textAlign: 'center',
          lineHeight: fontSizes.md * lineHeights.normal,
        }}
      >
        {isModel
          ? "Pick from one of the providers you've already connected."
          : 'Add an LLM provider (cloud or local Ollama) to start chatting.'}
      </Text>
      <View style={{ marginTop: space.s4 }}>
        <Button
          title={isModel ? 'Pick a model' : 'Set up provider'}
          size="lg"
          onPress={isModel ? onPickModel : onSetupProvider}
        />
      </View>
    </View>
  );
}

export default function ProfileChat() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const { endpoint, call } = useEndpoint();
  const summaries = useProfileSummaries();
  const sessionsList = useSessionsList(id);

  const profile = useMemo(
    () => summaries.data?.profiles?.find((p) => p.name === id) ?? null,
    [summaries.data, id],
  );

  const latestChatId =
    profile?.latest_session?.kind === 'chat' ? profile.latest_session.id : null;
  const [sessionId, setSessionId] = useState(latestChatId);
  const [sessionPicked, setSessionPicked] = useState(false);
  // Seed-only — once sessionId is set we stop watching latestChatId so a later session_changed can't yank the user into a different chat mid-conversation.
  useEffect(() => {
    if (sessionPicked || sessionId) return;
    if (latestChatId) {
      setSessionId(latestChatId);
      return;
    }
    const sessions = sessionsList.data?.sessions ?? [];
    const chat = sessions.find((s) => (s.kind ?? 'chat') === 'chat');
    if (chat?.id) setSessionId(chat.id);
  }, [sessionPicked, sessionId, latestChatId, sessionsList.data]);
  const session = useSession(id, sessionId);

  const latestSessionTs =
    profile?.latest_session?.updated_at ??
    profile?.latest_session?.mtime ??
    profile?.latest_session?.started_at ??
    0;
  useEffect(() => {
    if (!profile?.name || !latestSessionTs) return;
    markProfileRead(endpoint?.id, profile.name, latestSessionTs);
  }, [endpoint?.id, profile?.name, latestSessionTs]);

  const [ctxWindow, setCtxWindow] = useState(null);
  useEffect(() => {
    if (!endpoint || !profile?.name || !profile?.model) {
      setCtxWindow(null);
      return undefined;
    }
    let cancelled = false;
    call('host.model.ctx_window', { profile: profile.name, model: profile.model })
      .then((r) => {
        if (cancelled) return;
        setCtxWindow(Number(r?.ctx_window) || null);
      })
      .catch(() => {
        if (!cancelled) setCtxWindow(null);
      });
    return () => {
      cancelled = true;
    };
  }, [endpoint, profile?.name, profile?.model, call]);

  const hydrating =
    (sessionId && (session.loading || session.data === null)) ||
    (!sessionId && sessionsList.loading && sessionsList.data === null);

  const toast = useToast();
  const [actionTarget, setActionTarget] = useState(null);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const micUnavailable = () => toast({ title: 'Voice messages coming soon', kind: 'info', duration: 1800 });

  const accent = profile?.accent ?? colors.ink3;

  const { send: streamSend, pendingTurn, isStreaming } = useChatSend({
    profile: id,
    sessionId,
    onCompleted: ({ sessionId: streamSid } = {}) => {
      if (streamSid && streamSid !== sessionId) {
        setSessionPicked(true);
        setSessionId(streamSid);
      }
      return Promise.all([sessionsList.refresh(), session.refresh()]);
    },
  });

  useEventEffect('session_changed', (ev) => {
    if (ev.data?.profile === id) {
      sessionsList.refresh();
      session.refresh();
    }
  });

  const sendMessage = (text) => streamSend(text);

  if (!endpoint) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="profile" accent={colors.ink3} title={`@${id}`} meta="not paired" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ color: colors.ink3 }}>Pair this phone to a daemon first.</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (summaries.loading && !profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="profile" accent={colors.ink3} title={`@${id}`} meta="loading…" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      </SafeAreaView>
    );
  }

  if (!profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="profile" accent={colors.ink3} title={`@${id}`} meta="profile · not found" onBack={() => router.back()} />
      </SafeAreaView>
    );
  }

  const emptyState = profileEmptyState(profile); // 'ready' | 'needs-model' | 'needs-provider'
  const blocked = emptyState !== 'ready';
  // Format helpers — fmtTokens compacts to K / M like desktop ProfileChatHeader fmtCount.
  const fmtTokens = (n) => {
    if (!n) return '0';
    if (n < 1000) return `${n}`;
    if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}K`;
    return `${(n / 1_000_000).toFixed(1)}M`;
  };
  const ctxUsed = session.data?.last_ctx_tokens ?? 0;
  const headerMeta =
    emptyState === 'needs-provider'
      ? 'profile · no provider'
      : emptyState === 'needs-model'
        ? 'profile · pick a model'
        : [
            profile.model && profile.model.split('/').slice(1).join('/'),
            ctxWindow && ctxWindow > 0
              ? `${fmtTokens(ctxUsed)}/${fmtTokens(ctxWindow)} ctx`
              : null,
            profile.budget_daily_usd != null
              ? `$${(profile.budget_used_usd ?? 0).toFixed(2)}/$${Number(profile.budget_daily_usd).toFixed(2)}`
              : null,
          ]
            .filter(Boolean)
            .join(' · ');

  const turns = session.data?.turns ?? [];

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ChatHeader
        kind="profile"
        accent={accent}
        title={profile.name}
        meta={headerMeta}
        onBack={() => router.back()}
        onMore={() => router.push(`/profile/${profile.name}/settings`)}
        onPickSession={() => setSessionsOpen(true)}
      />
      {blocked ? (
        <NeedsSetup
          name={profile.name}
          accent={accent}
          state={emptyState}
          onSetupProvider={() => router.push(`/profile/${profile.name}/providers`)}
          onPickModel={() => router.push(`/profile/${profile.name}/settings`)}
        />
      ) : (
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
          <ChatList
            turns={turns}
            pendingTurn={pendingTurn}
            loading={session.loading}
            hydrating={hydrating}
            profileName={profile.name}
            model={profile.model}
            accent={accent}
            onActionTarget={setActionTarget}
            colors={colors}
            fonts={fonts}
            fontSizes={fontSizes}
          />
          <Composer
            placeholder={`Message @${profile.name}…`}
            accent={accent}
            onSend={sendMessage}
            onMicPress={micUnavailable}
            onMicLongPress={micUnavailable}
          />
        </KeyboardAvoidingView>
      )}
      <MessageActionsSheet target={actionTarget} onClose={() => setActionTarget(null)} />
      <SessionsSheet
        open={sessionsOpen}
        onClose={() => setSessionsOpen(false)}
        profile={profile.name}
        accent={accent}
        activeSessionId={sessionId}
        onPick={(sid) => {
          setSessionPicked(true);
          setSessionId(sid);
        }}
        onNew={() => {
          setSessionPicked(true);
          setSessionId(null);
        }}
      />
    </SafeAreaView>
  );
}
