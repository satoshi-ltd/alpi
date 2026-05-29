import { useLocalSearchParams, useRouter } from 'expo-router';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../src/theme/tokens';

import { AlpiMark } from '../../src/components/AlpiMark';
import { Button } from '../../src/components/Button';
import { useToast } from '../../src/components/Toast';
import { ProfileAssistantMessage, ProfileUserMessage } from '../../src/features/chat/Bubble';
import { ChatHeader } from '../../src/features/chat/ChatHeader';
import { Composer } from '../../src/features/chat/Composer';
import { MessageActionsSheet } from '../../src/features/chat/MessageActionsSheet';
import { retryTextFor } from '../../src/features/chat/messageActions';
import { mergeStreamingTurn } from '../../src/features/chat/chatTurns';
import { ChatSkeleton } from '../../src/features/chat/ChatSkeleton';
import { MessageSkeleton } from '../../src/components/MessageSkeleton';
import { ToolCallGroup, groupConsecutiveTools } from '../../src/features/chat/ToolCallRow';
import { askUserNoAnswerTag } from '../../src/features/chat/askUserAnswer';
import { Diamond } from '../../src/components/Diamond';
import { SessionsSheet } from '../../src/features/sheets/SessionsSheet';
import { useChatSend } from '../../src/hooks/useChatSend';
import { useProfileSummaries, useSession, useSessionsList } from '../../src/hooks/useDaemonData';
import { useEventEffect } from '../../src/hooks/useEvents';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { profileEmptyState } from '../../src/lib/profileReady';
import { markProfileRead } from '../../src/lib/readState';
import { useTheme } from '../../src/theme/ThemeContext';
import { useCanAdminEarly } from '../../src/hooks/useActiveRole';

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
  emptyHeading: { fontSize: fontSizes["2xl"], lineHeight: 26, letterSpacing: -0.018 * 22, textAlign: 'center' },
  emptyModel: { fontSize: fontSizes.sm, textAlign: 'center' },
});

const TurnBlock = memo(function TurnBlock({ turn, turnIndex, accent, colors, fonts, fontSizes, onActionTarget }) {
  const ts = turn.at ? relativeTime(turn.at * 1000) : '';
  const askUsers = (turn.tools ?? []).filter((t) => t.name === 'ask_user');
  const otherTools = (turn.tools ?? []).filter((t) => t.name !== 'ask_user');
  const askUserAnswers = askUsers
    .map((t) => ({
      tool_id: t.tool_id,
      result: (t.output || t.result || '').trim(),
      question: t.args?.question || '',
    }))
    .filter((t) => t.result);
  const lastAnswer = askUserAnswers[askUserAnswers.length - 1]?.result;
  // Suppress only on exact echo; useful commentary after cancel/timeout/no-handler stays visible.
  const assistantEchoesAsk = lastAnswer && turn.assistant?.trim() === lastAnswer;
  const showAssistant = !!turn.assistant && !assistantEchoesAsk;
  return (
    <View style={TURN_STYLES.block}>
      {turn.user ? (
        <ProfileUserMessage
          text={turn.user}
          ts={ts}
          accent={accent}
          onLongPress={() => onActionTarget({ kind: 'user', text: turn.user, turnIndex })}
        />
      ) : null}
      {otherTools.length ? (
        <View style={TURN_STYLES.tools}>
          {groupConsecutiveTools(otherTools).map((g, i) => (
            <ToolCallGroup key={`g-${i}-${g.tools[0].tool_id ?? g.name}`} group={g} accent={accent} />
          ))}
        </View>
      ) : null}
      {askUserAnswers.map((a) => (
        <AskUserAnswer
          key={a.tool_id ?? a.result}
          result={a.result}
          question={a.question}
          accent={accent}
          colors={colors}
          fonts={fonts}
          fontSizes={fontSizes}
        />
      ))}
      {showAssistant ? (
        <ProfileAssistantMessage
          text={turn.assistant}
          onLongPress={() => onActionTarget({
            kind: 'agent',
            text: turn.assistant,
            retryText: turn.user,
            turnIndex,
          })}
        />
      ) : turn.pending && !otherTools.length && !askUsers.length ? (
        <View style={TURN_STYLES.thinkingHolder}>
          <MessageSkeleton />
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

function AskUserAnswer({ result, question, accent, colors, fonts, fontSizes }) {
  const noAnswerTag = askUserNoAnswerTag(result);
  if (noAnswerTag) {
    return (
      <View style={{ paddingHorizontal: space.s7 }}>
        <View
          style={{
            borderRadius: radii.md,
            borderWidth: 0.5,
            borderColor: colors.line,
            paddingHorizontal: space.s5,
            paddingVertical: space.s4,
            gap: space.s2,
          }}
        >
          <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.lg, color: colors.ink3 }}>
            {question || result}
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>∅</Text>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, letterSpacing: 0.6 }}>
              {noAnswerTag}
            </Text>
          </View>
        </View>
      </View>
    );
  }
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, paddingHorizontal: space.s7 }}>
      <Diamond color={accent ?? colors.ink3} size="md" />
      <Text
        style={{
          flex: 1,
          fontFamily: fonts.sans.regular,
          fontSize: fontSizes.lg,
          color: colors.ink,
        }}
      >
        {result}
      </Text>
    </View>
  );
}

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

  const full = useMemo(() => mergeStreamingTurn(turns, pendingTurn), [turns, pendingTurn]);

  const visible = useMemo(() => {
    const start = Math.max(0, full.length - pageSize);
    const out = [];
    for (let i = full.length - 1; i >= start; i -= 1) {
      out.push({ turn: full[i], turnIndex: i });
    }
    return out;
  }, [full, pageSize]);
  const hasMore = full.length > pageSize;

  const renderItem = useCallback(
    ({ item }) => (
      <TurnBlock
        turn={item.turn}
        turnIndex={item.turnIndex}
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
      keyExtractor={(item, idx) => `${item.turn.user ?? ''}|${item.turnIndex}|${idx}`}
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
  const action = isModel ? onPickModel : onSetupProvider;
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
        {action
          ? isModel
            ? "Pick from one of the providers you've already connected."
            : 'Add an LLM provider (cloud or local Ollama) to start chatting.'
          : 'Ask the host admin to finish setting up this profile.'}
      </Text>
      {action ? (
        <View style={{ marginTop: space.s4 }}>
          <Button
            title={isModel ? 'Pick a model' : 'Set up provider'}
            size="lg"
            onPress={action}
          />
        </View>
      ) : null}
    </View>
  );
}

export default function ProfileChat() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const canAdmin = useCanAdminEarly();
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

  const sendMessage = (text, options) => streamSend(text, options);
  const [composerSeed, setComposerSeed] = useState(null);
  const [pendingRewriteIndex, setPendingRewriteIndex] = useState(null);
  const onEditTarget = (target) => {
    setComposerSeed({ text: target.text ?? '', key: Date.now() });
    setPendingRewriteIndex(Number.isInteger(target.turnIndex) ? target.turnIndex : null);
    setActionTarget(null);
  };
  const onRetryTarget = (target) => {
    setActionTarget(null);
    const text = retryTextFor(target);
    if (!text) return;
    const opts = Number.isInteger(target.turnIndex) ? { rewriteFromTurn: target.turnIndex } : undefined;
    sendMessage(text, opts);
  };
  const onComposerSend = (text) => {
    const opts = Number.isInteger(pendingRewriteIndex) ? { rewriteFromTurn: pendingRewriteIndex } : undefined;
    setPendingRewriteIndex(null);
    sendMessage(text, opts);
  };

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
        onMore={canAdmin ? () => router.push(`/profile/${profile.name}/settings`) : null}
        onPickSession={() => setSessionsOpen(true)}
      />
      {blocked ? (
        <NeedsSetup
          name={profile.name}
          accent={accent}
          state={emptyState}
          onSetupProvider={canAdmin ? () => router.push(`/profile/${profile.name}/providers`) : null}
          onPickModel={canAdmin ? () => router.push(`/profile/${profile.name}/settings`) : null}
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
            onSend={onComposerSend}
            onMicPress={micUnavailable}
            onMicLongPress={micUnavailable}
            seedText={composerSeed?.text}
            seedKey={composerSeed?.key}
          />
        </KeyboardAvoidingView>
      )}
      <MessageActionsSheet
        target={actionTarget}
        onClose={() => setActionTarget(null)}
        onEdit={onEditTarget}
        onRetry={onRetryTarget}
      />
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
