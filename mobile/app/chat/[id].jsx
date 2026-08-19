import { useLocalSearchParams, useRouter } from 'expo-router';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import { KeyboardPane } from '../../src/components/KeyboardPane';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space } from '../../src/theme/tokens';

import { ActionSheet } from '../../src/components/ActionSheet';
import { AlpiMark } from '../../src/components/AlpiMark';
import { Banner } from '../../src/components/Banner';
import { Button } from '../../src/components/Button';
import { Meter } from '../../src/components/Meter';
import { useToast } from '../../src/components/Toast';
import { ProfileAssistantMessage, ProfileUserMessage } from '../../src/features/chat/Bubble';
import { Reasoning } from '../../src/features/chat/Reasoning';
import { turnParts } from '../../src/features/chat/reasoningSteps';
import { ChatHeader, headerMenuActions } from '../../src/features/chat/ChatHeader';
import { SoundWave } from '../../src/features/chat/SoundWave';
import { enqueueReadAloud } from '../../src/lib/readAloud';
import { Composer } from '../../src/features/chat/Composer';
import { MessageActionsSheet } from '../../src/features/chat/MessageActionsSheet';
import { retryTextFor } from '../../src/features/chat/messageActions';
import { visibleWindow } from '../../src/lib/chatWindow';
import { compactProducedTool } from '../../src/lib/producedAttachments';
import { modelLabel } from '../../src/lib/modelLabel';
import { profileLabel } from '../../src/lib/profileLabel';
import { mergeStreamingTurn, isInterruptedTurn, isLastTurnInFlight, consumeAutoRead, routedModelFor, baselineModelFor, turnFrontier, turnLandedSince } from '../../src/features/chat/chatTurns';
import { ChatSkeleton } from '../../src/features/chat/ChatSkeleton';
import { EmptyThread } from '../../src/features/chat/EmptyThread';
import { ToolModule } from '../../src/features/chat/ToolCallRow';
import { askUserNoAnswerTag } from '../../src/features/chat/askUserAnswer';
import { Diamond } from '../../src/components/Diamond';
import { SessionsSheet } from '../../src/features/sheets/SessionsSheet';
import { useChatSend } from '../../src/hooks/useChatSend';
import { oversizeError, resolveAttachmentMime, stageAttachment } from '../../src/lib/attachments';
import { useProfileSummaries, useSessionsList } from '../../src/hooks/useDaemonData';
import { isMissingSession, useSessionTranscript } from '../../src/hooks/useSessionTranscript';
import { useDebouncedCallback } from '../../src/hooks/useDebouncedCallback';
import { useEventEffect } from '../../src/hooks/useEvents';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { isForeignConnection } from '../../src/features/aln/deeplink';
import { CONTENT_MAX_W, PANE_PAD_X } from '../../src/lib/panes';
import { profileEmptyState } from '../../src/lib/profileReady';
import { markProfileRead } from '../../src/lib/readState';
import { usePane } from '../../src/nav/PaneContext';
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
  listContent: { paddingTop: space.s5, paddingBottom: space.s5 },
  contentColumn: { alignSelf: 'center', width: '100%', maxWidth: CONTENT_MAX_W },
  steps: { gap: space.s2 },
  tools: { gap: space.s1 },
  error: { paddingHorizontal: PANE_PAD_X },
  unfinished: { paddingHorizontal: PANE_PAD_X },
  routedModel: { paddingHorizontal: PANE_PAD_X },
});

function PaneColumn({ children }) {
  const { twoPane } = usePane();
  return twoPane ? <View style={TURN_STYLES.contentColumn}>{children}</View> : children;
}

const TurnBlock = memo(function TurnBlock({ turn, turnIndex, profileName, profileModel, accent, colors, fonts, fontSizes, onActionTarget, inFlight = false }) {
  const ts = turn.at ? relativeTime(turn.at * 1000) : '';
  const parts = turnParts(turn);
  const lastAnswer = parts.askUsers[parts.askUsers.length - 1]?.result;
  // Suppress only on exact echo; useful commentary after cancel/timeout/no-handler stays visible.
  const assistantEchoesAsk = lastAnswer && turn.assistant?.trim() === lastAnswer;
  const showAssistant = (!!turn.assistant || turn.output_attachments?.length > 0) && !assistantEchoesAsk;
  const routedModel = routedModelFor(turn, profileModel);
  const active = turn.pending && !showAssistant;
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
      {(parts.tools.length > 0 || parts.askUsers.length > 0 || parts.reasoning || active) ? (
        <View style={TURN_STYLES.steps}>
          {parts.tools.length > 0 ? (
            <ToolModule
              tools={parts.tools.map((t) => compactProducedTool(t, turn.output_attachments))}
              accent={accent}
            />
          ) : null}
          {parts.askUsers.map((a, i) => (
            <AskUserAnswer
              key={`a-${a.tool_id ?? i}`}
              result={a.result}
              question={a.question}
              accent={accent}
              colors={colors}
              fonts={fonts}
              fontSizes={fontSizes}
            />
          ))}
          {(parts.reasoning || active) ? (
            <Reasoning
              text={parts.reasoning}
              seconds={parts.reasonedSeconds}
              streaming={active}
              flat
            />
          ) : null}
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
      {showAssistant && routedModel ? (
        <Text style={[TURN_STYLES.routedModel, { color: colors.ink3, fontFamily: fonts.mono, fontSize: fontSizes.xs }]}>
          ⇢ {routedModel}
        </Text>
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
      <View style={{ paddingHorizontal: PANE_PAD_X }}>
        <View
          style={{
            borderRadius: radii.lg,
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
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, paddingHorizontal: PANE_PAD_X }}>
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

function ChatList({ turns, pendingTurn, hydrating, profileName, model, accent, onActionTarget, colors, fonts, fontSizes, turnsBase = 0, hasMoreRemote = false, onLoadOlder, sessionInFlight = false }) {
  const [pageSize, setPageSize] = useState(INITIAL_PAGE);
  const { twoPane } = usePane();

  const full = useMemo(
    () => mergeStreamingTurn(turns, pendingTurn),
    [turns, pendingTurn],
  );
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
        profileModel={model}
        accent={accent}
        colors={colors}
        fonts={fonts}
        fontSizes={fontSizes}
        onActionTarget={onActionTarget}
        inFlight={lastTurnInFlight && item.turnIndex === lastTurnIndex}
      />
    ),
    [profileName, model, accent, colors, fonts, fontSizes, onActionTarget, lastTurnInFlight, lastTurnIndex],
  );

  if (hydrating && full.length === 0) {
    return <ChatSkeleton kind="profile" accent={accent} />;
  }
  if (full.length === 0) {
    return (
      <EmptyThread
        heading={`start a thread with ${profileLabel(profileName)}`}
        detail={modelLabel(model)}
        accent={accent}
      />
    );
  }

  return (
    <FlatList
      inverted
      data={visible}
      keyExtractor={(item) => String(item.turnIndex)}
      renderItem={renderItem}
      contentContainerStyle={twoPane ? [TURN_STYLES.listContent, TURN_STYLES.contentColumn] : TURN_STYLES.listContent}
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
  const { colors, fonts } = useTheme();
  const { activeId } = useEndpoint();
  if (isForeignConnection(activeId, connectionId)) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ChatHeader kind="profile" accent={colors.ink3} title={`@${profileLabel(id)}`} meta="other connection" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10 }}>
          <Text style={{ fontFamily: fonts.sans.regular, color: colors.ink3, textAlign: 'center' }}>
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
  const { endpoint, call, probeState } = useEndpoint();
  const summaries = useProfileSummaries();
  const sessionsList = useSessionsList(id);

  const daemonStatus = endpoint ? probeState?.get(endpoint.id) ?? 'unknown' : 'offline';
  const daemonDown =
    !!endpoint && (daemonStatus === 'offline' || daemonStatus === 'disabled' || daemonStatus === 'auth-failed');

  const profile = useMemo(
    () => summaries.data?.profiles?.find((p) => p.name === id) ?? null,
    [summaries.data, id],
  );

  const latestChatId =
    profile?.latest_session?.kind === 'chat' ? profile.latest_session.id : null;
  const seedSessionId = useMemo(() => {
    if (latestChatId) return latestChatId;
    const sessions = sessionsList.data?.sessions ?? [];
    return sessions.find((s) => (s.kind ?? 'chat') === 'chat')?.id ?? null;
  }, [latestChatId, sessionsList.data]);

  const [sessionId, setSessionId] = useState(sid || latestChatId);
  const [sessionPicked, setSessionPicked] = useState(false);
  // Seed-only — once sessionId is set we stop watching latestChatId so a later session_changed can't yank the user into a different chat mid-conversation.
  useEffect(() => {
    if (sessionPicked || sessionId || !seedSessionId) return;
    setSessionId(seedSessionId);
  }, [sessionPicked, sessionId, seedSessionId]);
  const session = useSessionTranscript(id, sessionId);
  // latest_session in host.profile.summaries is connection-agnostic, so it can seed a session this connection may neither read nor post to.
  useEffect(() => {
    if (!sessionId || !isMissingSession(session.error)) return;
    setSessionPicked(true);
    setSessionId(null);
  }, [sessionId, session.error]);
  const sessionData = session.data;
  const turnsBase = session.turnsOffset;
  const totalTurns = session.totalTurns;
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

  const hydrating = sessionId
    ? !session.settled
    : !sessionPicked && (!!seedSessionId || (sessionsList.loading && !sessionsList.data));

  const toast = useToast();
  const [actionTarget, setActionTarget] = useState(null);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const accent = profile?.accent ?? colors.ink3;

  const { send: streamSend, cancel: streamCancel, isSending, pendingTurn, isStreaming } = useChatSend({
    profile: id,
    sessionId,
    onCompleted: async ({ sessionId: streamSid, baseline } = {}) => {
      if (streamSid && streamSid !== sessionId) {
        setSessionPicked(true);
        setSessionId(streamSid);
      }
      sessionsList.refresh();
      const snap = await session.refresh(streamSid || sessionId);
      if (turnLandedSince(snap, baseline)) return true;
      toast({ title: 'Answer saved, not shown', message: 'The transcript did not load — pull to refresh.', duration: 2600 });
      return false;
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
        profile: id,
      });
    }
  }, [pendingTurn, voiceCfg, sessionData, turnsBase, call, id, accent]);

  const sendMessage = (text, options) => {
    if (profile?.paused || daemonDown || isSending()) return;
    streamSend(text, {
      ...options,
      baseline: turnFrontier({ data: sessionData, turnsOffset: turnsBase, totalTurns }),
    });
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
        type: '*/*',
        multiple: false,
        copyToCacheDirectory: true,
      });
      if (res.canceled) return;
      const asset = res.assets?.[0];
      if (!asset) return;
      if (Number.isFinite(asset.size) && asset.size > 0) {
        const err = oversizeError(asset.name, resolveAttachmentMime(asset.name, asset.mimeType), asset.size);
        if (err) throw new Error(err);
      }
      const { readAsStringAsync } = await import('expo-file-system/legacy').catch(() => import('expo-file-system'));
      const base64 = await readAsStringAsync(asset.uri, { encoding: 'base64' });
      const staged = await stageAttachment(call, {
        profile: profile.name, name: asset.name, mime: asset.mimeType, base64,
        size: asset.size,
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
          <Text style={{ fontFamily: fonts.sans.regular, color: colors.ink3 }}>Pair this phone to a daemon first.</Text>
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
  const budgetCap = Number(profile.budget_daily_usd ?? 0);
  const budgetUsed = Number(profile.budget_used_usd ?? 0);
  const shownModel = modelLabel(profile.model);
  const headerMeta =
    emptyState === 'needs-provider'
      ? 'profile · no provider'
      : emptyState === 'needs-model'
        ? 'profile · pick a model'
        : (
            <>
              {shownModel ? (
                <Text
                  numberOfLines={1}
                  style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink2 }}
                >
                  {shownModel}
                </Text>
              ) : null}
              {ctxWindow && ctxWindow > 0 ? (
                <Meter
                  label="Context window"
                  value={fmtTokens(ctxUsed)}
                  tail={`/${fmtTokens(ctxWindow)}`}
                  pct={ctxUsed / ctxWindow}
                  color={accent}
                />
              ) : null}
              {budgetCap > 0 ? (
                <Meter
                  label="Daily budget"
                  value={`$${budgetUsed.toFixed(2)}`}
                  tail={`/$${budgetCap.toFixed(2)}`}
                  pct={budgetUsed / budgetCap}
                  color={accent}
                />
              ) : null}
            </>
          );

  const turns = sessionData?.turns ?? [];
  const paused = !!profile.paused;

  const menuActions = headerMenuActions({
    noun: 'profile',
    paused,
    autoRead: voiceCfg.autoRead,
    onOpenSettings: canAdmin ? () => router.push(`/profile/${profile.name}/settings`) : null,
    onTogglePause: canAdmin
      ? () =>
          call('host.config.set_field', { profile: id, key: 'paused', value: paused ? 'false' : 'true' })
            .then(() => summaries.refresh())
            .catch((e) => toast({ title: paused ? 'Resume failed' : 'Pause failed', message: String(e) }))
      : null,
    onToggleAutoRead: canAdmin
      ? () =>
          call('host.voice.set_auto_read', { profile: id, enabled: !voiceCfg.autoRead })
            .then(loadVoiceCfg)
            .catch((e) => toast({ title: 'auto-read failed', message: String(e) }))
      : null,
    onOpenSkills: canAdmin ? () => router.push(`/profile/${profile.name}/brain/skills`) : null,
    onOpenMemory: canAdmin ? () => router.push(`/profile/${profile.name}/brain/memory`) : null,
    onOpenTools: canAdmin ? () => router.push(`/profile/${profile.name}/brain/tools`) : null,
    onOpenSchedule: canAdmin ? () => router.push(`/profile/${profile.name}/schedule`) : null,
    onRefresh: () => {
      sessionsList.refresh();
      session.refresh();
    },
  });

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ChatHeader
        kind="profile"
        accent={accent}
        title={profileLabel(profile.name)}
        meta={headerMeta}
        onBack={() => router.back()}
        onMore={() => setMenuOpen(true)}
        onPickSession={() => setSessionsOpen(true)}
        right={<SoundWave accent={accent} />}
      />
      {daemonStatus === 'offline' ? (
        <Banner kind="danger" action="Retry" onAction={() => session.refresh()}>
          Daemon unreachable. Reconnecting…
        </Banner>
      ) : daemonStatus === 'disabled' ? (
        <Banner kind="warning">
          Connection disabled by host. Ask an admin to enable it in Settings → Connections.
        </Banner>
      ) : daemonStatus === 'auth-failed' ? (
        <Banner kind="danger">
          Token rejected by daemon. Re-pair this phone to continue.
        </Banner>
      ) : null}
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
        <KeyboardPane>
          <ChatList
            turns={turns}
            pendingTurn={pendingTurn}
            hydrating={hydrating}
            profileName={profile.name}
            model={baselineModelFor(sessionData, profile.model)}
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
          <PaneColumn>
            <Composer
              placeholder={`Message @${profileLabel(profile.name)}…`}
              accent={accent}
              disabled={paused || daemonDown}
              busy={isStreaming}
              onStop={streamCancel}
              onSend={onComposerSend}
              seedText={composerSeed?.text}
              seedKey={composerSeed?.key}
              attachments={attachments}
              onPickAttachment={pickAttachment}
              onRemoveAttachment={(i) => setAttachments((p) => p.filter((_, j) => j !== i))}
            />
          </PaneColumn>
        </KeyboardPane>
      )}
      <ActionSheet
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        title={`@${profileLabel(profile.name)}`}
        subtitle="PROFILE"
        actions={menuActions}
      />
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
