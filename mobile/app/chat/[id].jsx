import { useLocalSearchParams, useRouter } from 'expo-router';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../src/theme/tokens';

import { AlpiMark } from '../../src/components/AlpiMark';
import { Button } from '../../src/components/Button';
import { useToast } from '../../src/components/Toast';
import { ProfileAssistantMessage, ProfileUserMessage } from '../../src/features/chat/Bubble';
import { Reasoning } from '../../src/features/chat/Reasoning';
import { reasoningSteps } from '../../src/features/chat/reasoningSteps';
import { ChatHeader } from '../../src/features/chat/ChatHeader';
import { SoundWave } from '../../src/features/chat/SoundWave';
import { enqueueReadAloud } from '../../src/lib/readAloud';
import { Composer } from '../../src/features/chat/Composer';
import { MessageActionsSheet } from '../../src/features/chat/MessageActionsSheet';
import { retryTextFor } from '../../src/features/chat/messageActions';
import { visibleWindow } from '../../src/lib/chatWindow';
import { compactProducedTool } from '../../src/lib/producedAttachments';
import { profileLabel } from '../../src/lib/profileLabel';
import { mergeStreamingTurn, isInterruptedTurn, isLastTurnInFlight, consumeAutoRead } from '../../src/features/chat/chatTurns';
import { ChatSkeleton } from '../../src/features/chat/ChatSkeleton';
import { ToolCallGroup, groupConsecutiveTools } from '../../src/features/chat/ToolCallRow';
import { askUserNoAnswerTag } from '../../src/features/chat/askUserAnswer';
import { Diamond } from '../../src/components/Diamond';
import { SessionsSheet } from '../../src/features/sheets/SessionsSheet';
import { useChatSend } from '../../src/hooks/useChatSend';
import { stageAttachment } from '../../src/lib/attachments';
import { useProfileSummaries, useSessionsList } from '../../src/hooks/useDaemonData';
import { useSessionTranscript } from '../../src/hooks/useSessionTranscript';
import { useDebouncedCallback } from '../../src/hooks/useDebouncedCallback';
import { useEventEffect } from '../../src/hooks/useEvents';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { isForeignConnection } from '../../src/features/aln/deeplink';
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
  steps: { gap: space.s2 },
  tools: { gap: space.s1 },
  error: { paddingHorizontal: space.s7 },
  unfinished: { paddingHorizontal: space.s7 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.s10, gap: space.s10 },
  emptyTextWrap: { gap: space.s4, alignItems: 'center' },
  emptyHeading: { fontSize: fontSizes["2xl"], lineHeight: 26, letterSpacing: -0.018 * 22, textAlign: 'center' },
  emptyModel: { fontSize: fontSizes.sm, textAlign: 'center' },
});

const TurnBlock = memo(function TurnBlock({ turn, turnIndex, profileName, accent, colors, fonts, fontSizes, onActionTarget, inFlight = false }) {
  const ts = turn.at ? relativeTime(turn.at * 1000) : '';
  const askUsers = (turn.tools ?? []).filter((t) => t.name === 'ask_user');
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
  const showAssistant = (!!turn.assistant || turn.output_attachments?.length > 0) && !assistantEchoesAsk;
  const steps = reasoningSteps(turn, { active: turn.pending && !showAssistant });
  return (
    <View style={TURN_STYLES.block}>
      {turn.user ? (
        <ProfileUserMessage
          text={turn.user}
          ts={ts}
          accent={accent}
          attachments={turn.attachments}
          profile={profileName}
          onLongPress={() => onActionTarget({ kind: 'user', text: turn.user, turnIndex })}
        />
      ) : null}
      {steps.length > 0 ? (
        <View style={TURN_STYLES.steps}>
          {steps.map((step, i) => {
            if (step.kind === 'reasoning') {
              return (
                <Reasoning
                  key={`r-${i}`}
                  text={step.text}
                  seconds={step.seconds}
                  streaming={turn.pending && step.trailing}
                />
              );
            }
            if (step.kind === 'askUser') {
              return step.result ? (
                <AskUserAnswer
                  key={`a-${i}`}
                  result={step.result}
                  question={step.question}
                  accent={accent}
                  colors={colors}
                  fonts={fonts}
                  fontSizes={fontSizes}
                />
              ) : null;
            }
            const tools = step.tools.map((t) => compactProducedTool(t, turn.output_attachments));
            return (
              <View key={`t-${i}`} style={TURN_STYLES.tools}>
                {groupConsecutiveTools(tools).map((g, j) => (
                  <ToolCallGroup key={`g-${j}-${g.tools[0].tool_id ?? g.name}`} group={g} accent={accent} />
                ))}
              </View>
            );
          })}
        </View>
      ) : null}
      {showAssistant ? (
        <ProfileAssistantMessage
          text={turn.assistant}
          attachments={turn.output_attachments}
          profile={profileName}
          onLongPress={() => onActionTarget({
            kind: 'agent',
            text: turn.assistant,
            retryText: turn.user,
            turnIndex,
          })}
        />
      ) : null}
      {isInterruptedTurn(turn) ? (
        <Text style={[TURN_STYLES.unfinished, { color: colors.ink3, fontFamily: fonts.mono, fontSize: fontSizes.xs }]}>
          Interrupted before final reply
        </Text>
      ) : null}
      {!isInterruptedTurn(turn) && inFlight ? (
        <Text style={[TURN_STYLES.unfinished, { color: colors.ink3, fontFamily: fonts.mono, fontSize: fontSizes.xs }]}>
          Still working…
        </Text>
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
          start a thread with @{profileLabel(profileName)}
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

function ChatList({ turns, pendingTurn, loading, hydrating, profileName, model, accent, onActionTarget, colors, fonts, fontSizes, turnsBase = 0, hasMoreRemote = false, onLoadOlder, sessionInFlight = false }) {
  const [pageSize, setPageSize] = useState(INITIAL_PAGE);

  const full = useMemo(() => mergeStreamingTurn(turns, pendingTurn), [turns, pendingTurn]);
  const lastTurnInFlight = useMemo(
    () => isLastTurnInFlight(full, sessionInFlight),
    [full, sessionInFlight],
  );
  const lastTurnIndex = turnsBase + full.length - 1;

  const visible = useMemo(
    () => visibleWindow(full, pageSize, turnsBase),
    [full, pageSize, turnsBase],
  );
  const hasMore = full.length > pageSize || hasMoreRemote;

  const renderItem = useCallback(
    ({ item }) => (
      <TurnBlock
        turn={item.turn}
        turnIndex={item.turnIndex}
        profileName={profileName}
        accent={accent}
        colors={colors}
        fonts={fonts}
        fontSizes={fontSizes}
        onActionTarget={onActionTarget}
        inFlight={lastTurnInFlight && item.turnIndex === lastTurnIndex}
      />
    ),
    [profileName, accent, colors, fonts, fontSizes, onActionTarget, lastTurnInFlight, lastTurnIndex],
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
      keyExtractor={(item) => String(item.turnIndex)}
      renderItem={renderItem}
      contentContainerStyle={{ paddingTop: space.s5, paddingBottom: space.s5 }}
      onEndReached={hasMore ? () => {
        if (full.length <= pageSize && hasMoreRemote) onLoadOlder?.();
        setPageSize((n) => n + PAGE_STEP);
      } : undefined}
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
        @{profileLabel(name)} needs {isModel ? 'a model' : 'a provider'}
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
  const { id, connectionId, sid } = useLocalSearchParams();
  const router = useRouter();
  const { colors } = useTheme();
  const { activeId } = useEndpoint();
  if (isForeignConnection(activeId, connectionId)) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="profile" accent={colors.ink3} title={`@${profileLabel(id)}`} meta="other connection" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10 }}>
          <Text style={{ color: colors.ink3, textAlign: 'center' }}>
            This notification came from a connection that isn't active. Switch to it to open this chat.
          </Text>
        </View>
      </SafeAreaView>
    );
  }
  return <ProfileChatInner key={`${activeId ?? ''}:${id}:${sid ?? ''}`} />;
}

function ProfileChatInner() {
  const { id, sid } = useLocalSearchParams();
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
  const [sessionId, setSessionId] = useState(sid || latestChatId);
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
  const session = useSessionTranscript(id, sessionId);
  const sessionData = session.data;
  const turnsBase = session.turnsOffset;
  const sessionInFlight = session.inFlight;
  const hasMoreRemote = session.hasMore;
  const loadOlder = session.loadOlder;

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
    (sessionId && (session.loading || sessionData === null)) ||
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

  const refreshSession = useDebouncedCallback(() => {
    sessionsList.refresh();
    session.refresh();
  }, 400);
  useEventEffect('session_changed', (ev) => {
    if (ev.data?.profile === id) refreshSession();
  });

  const [voiceCfg, setVoiceCfg] = useState({ voiceId: null, autoRead: false });
  const loadVoiceCfg = useCallback(() => {
    if (!id) return;
    call('host.profile.detail', { profile: id })
      .then((d) => setVoiceCfg({ voiceId: d?.voice_id ?? null, autoRead: !!d?.voice_auto_read }))
      .catch(() => {});
  }, [id, call]);
  useEffect(() => { loadVoiceCfg(); }, [loadVoiceCfg]);
  useEventEffect('config_changed', (ev) => {
    if (ev?.data?.profile && ev.data.profile !== id) return;
    loadVoiceCfg();
  });

  const prevPendingRef = useRef(false);
  const lastPreviewRef = useRef('');
  // fire only on the pendingTurn truthy→null edge, never on history load
  useEffect(() => {
    if (pendingTurn?.assistant) lastPreviewRef.current = pendingTurn.assistant;
    const was = prevPendingRef.current;
    const now = !!pendingTurn;
    prevPendingRef.current = now;
    if (!(was && !now)) return;
    const ts = sessionData?.turns ?? [];
    const { speak, nextStreamed } = consumeAutoRead(lastPreviewRef.current, voiceCfg.autoRead, ts);
    lastPreviewRef.current = nextStreamed;
    if (speak) {
      const idx = turnsBase + ts.length - 1;
      enqueueReadAloud({
        call,
        key: `chat:${id}:${idx}`,
        voiceId: voiceCfg.voiceId || 'en-US-AriaNeural',
        text: speak,
        accent,
      });
    }
  }, [pendingTurn, voiceCfg, sessionData, turnsBase, call, id, accent]);

  const sendMessage = (text, options) => {
    if (profile?.paused) return;
    streamSend(text, options);
  };
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
  const [attachments, setAttachments] = useState([]);
  const pickAttachment = async () => {
    if (!profile?.name || !endpoint) return;
    try {
      const DocumentPicker = await import('expo-document-picker');
      const res = await DocumentPicker.getDocumentAsync({
        type: [
          'image/png', 'image/jpeg', 'image/webp', 'application/pdf',
          'text/plain', 'text/markdown', 'text/csv', 'application/json',
          'application/yaml', 'text/html',
        ],
        multiple: false,
        copyToCacheDirectory: true,
      });
      if (res.canceled) return;
      const asset = res.assets?.[0];
      if (!asset) return;
      const { readAsStringAsync } = await import('expo-file-system/legacy').catch(() => import('expo-file-system'));
      const base64 = await readAsStringAsync(asset.uri, { encoding: 'base64' });
      const staged = await stageAttachment(call, {
        profile: profile.name, name: asset.name, mime: asset.mimeType, base64,
      });
      setAttachments((prev) => [...prev, { ...staged, localUri: asset.uri }]);
    } catch (e) {
      toast({ title: 'Attachment failed', message: String(e?.message || e) });
    }
  };
  const onComposerSend = (text, atts) => {
    const opts = Number.isInteger(pendingRewriteIndex) ? { rewriteFromTurn: pendingRewriteIndex } : {};
    if (atts?.length) opts.attachments = atts;
    setPendingRewriteIndex(null);
    setAttachments([]);
    sendMessage(text, opts);
  };

  if (!endpoint) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="profile" accent={colors.ink3} title={`@${profileLabel(id)}`} meta="not paired" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ color: colors.ink3 }}>Pair this phone to a daemon first.</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (summaries.loading && !profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="profile" accent={colors.ink3} title={`@${profileLabel(id)}`} meta="loading…" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      </SafeAreaView>
    );
  }

  if (!profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="profile" accent={colors.ink3} title={`@${profileLabel(id)}`} meta="profile · not found" onBack={() => router.back()} />
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
  const ctxUsed = sessionData?.last_ctx_tokens ?? 0;
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

  const turns = sessionData?.turns ?? [];
  const paused = !!profile.paused;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ChatHeader
        kind="profile"
        accent={accent}
        title={profileLabel(profile.name)}
        meta={headerMeta}
        onBack={() => router.back()}
        onMore={canAdmin ? () => router.push(`/profile/${profile.name}/settings`) : null}
        onPickSession={() => setSessionsOpen(true)}
        right={<SoundWave accent={accent} />}
      />
      {paused ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, paddingHorizontal: space.s7, paddingVertical: space.s4, backgroundColor: `${colors.warning}22` }}>
          <Text numberOfLines={2} style={{ flex: 1, fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink2 }}>
            <Text style={{ fontFamily: fonts.sans.semibold ?? fonts.sans.medium, color: colors.ink }}>This profile is paused.</Text>
            {' '}You can read the history; resume from ··· to chat.
          </Text>
        </View>
      ) : null}
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
            turnsBase={turnsBase}
            hasMoreRemote={hasMoreRemote}
            onLoadOlder={loadOlder}
            sessionInFlight={sessionInFlight}
          />
          <Composer
            placeholder={`Message @${profileLabel(profile.name)}…`}
            accent={accent}
            disabled={paused}
            onSend={onComposerSend}
            onMicPress={micUnavailable}
            onMicLongPress={micUnavailable}
            seedText={composerSeed?.text}
            seedKey={composerSeed?.key}
            attachments={attachments}
            onPickAttachment={pickAttachment}
            onRemoveAttachment={(i) => setAttachments((p) => p.filter((_, j) => j !== i))}
          />
        </KeyboardAvoidingView>
      )}
      <MessageActionsSheet
        target={actionTarget}
        onClose={() => setActionTarget(null)}
        onEdit={paused ? null : onEditTarget}
        onRetry={paused ? null : onRetryTarget}
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
