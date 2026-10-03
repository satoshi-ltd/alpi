import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import ChatComposer from "../features/ChatComposer.jsx";
import AttachmentChips from "../primitives/AttachmentChips.jsx";
import { useProfileDetail } from "../hooks/useProfileDetail.js";
import { useSidecarTail } from "../hooks/useSidecarTail.js";
import Button from "../primitives/Button.jsx";
import Message from "../primitives/Message.jsx";
import { useStickyScroll } from "../lib/useStickyScroll.js";
import { useScrollProgress } from "../lib/useScrollProgress.js";
import { useScrollAnchor } from "../lib/useScrollAnchor.js";
import { useDelayedFlag } from "../lib/useDelayedFlag.js";
import RelativeTime from "../primitives/RelativeTime.jsx";
import { turnParts } from "../../../common/reasoningSteps.mjs";
import { fmtDuration } from "../../../common/reasoningLabel.mjs";
import { ProcessBlock } from "../features/ToolSteps.jsx";
import StreamingMarkdown from "../features/StreamingMarkdown.jsx";
import { InlineApproval, InlineClarification } from "../features/InlineRequest.jsx";
import { processTimeline } from "../lib/reasoningTimeline.js";
import { useFreshTurns } from "../lib/useFreshTurns.js";
import { profileLabel } from "../lib/profile-display.js";
import { ChatLoadSkeleton } from "./ChatSkeletons.jsx";
import SearchBar from "../primitives/SearchBar.jsx";
import { useTranscriptSearch } from "../hooks/useTranscriptSearch.js";
import { useContextWindow } from "../hooks/useContextWindow.js";
import { useNotify } from "../primitives/Notification.jsx";
import Markdown from "../primitives/Markdown.jsx";
import { ACCENT_HEXES } from "../../../common/accents.mjs";
import { FOLD_SIZES } from "../../../common/folds.mjs";
import ProducedImages from "../primitives/ProducedImages.jsx";
import { setImageRoots } from "../lib/imageRoots.js";
import { Banner, JumpToLatest, LoadFailed, MessageBubble, ProfileChatHeader } from "../primitives/index.js";
import { ProfileMessage } from "../primitives/index.js";
import {
  CopyIcon as DSCopyIcon,
  EditIcon,
  Fold,
  IconBtn,
  Kbd,
  Mono,
  RefreshBar,
  RefreshIcon,
  SpinnerIcon as DSSpinnerIcon,
  StopIcon,
  Tip,
  VolumeIcon,
} from "../primitives/index.js";
import { clearTtsQueue, currentlyPlayingKey, playTts, stopTts, subscribeTts, enqueueTts, VOICE_POOL } from "../lib/tts.js";
import { consumeAutoRead } from "../lib/autoRead.js";
import { useOnline } from "../lib/useOnline.js";
import styles from "./ChatPane.module.css";
import {
  compactProducedTool,
  imageProduced,
  nonImageProduced,
  stripProducedImageMarkdown,
} from "../lib/producedAttachments.js";
import { rewriteCut } from "../lib/rewriteCut.js";
import { dropInflightStub, isLastTurnInFlight } from "../lib/transcriptTurns.js";
import { copyText } from "../lib/clipboard.js";
import { pickEffectiveModel } from "../lib/effectiveModel.js";

export default function ChatPane({
  view,
  profiles,
  activeProfile,
  connectionId,
  sessionData,
  sessionSync = null,
  pendingTurn,
  onSend,
  onCancel,
  onConfigureProfile,
  onTogglePauseProfile,
  onRewriteMessage,
  onRetryMessage,
  rewriteDraft,
  onRewriteDraftApplied,
  pendingAttachment,
  onPendingAttachmentApplied,
  onOpenSkills,
  onOpenMemory,
  onOpenTools,
  onOpenSchedule,
  canManageProfileSurfaces = true,
  onNewSession,
  onChangeSession,
  sessionsOpenTick = 0,
  readAloudTick = 0,
  onRefreshSession,
  daemonOffline = false,
  searchOpen = false,
  onCloseSearch,
  loadError = null,
  onRetryLoad,
  inlineApprovals = null,
  inlineClarifications = null,
  onApprovalResolved,
  onClarificationResolved,
}) {
  const inline = useMemo(() => ({
    approvals: inlineApprovals ?? [],
    clarifications: inlineClarifications ?? [],
    onApprovalResolved,
    onClarificationResolved,
  }), [inlineApprovals, inlineClarifications, onApprovalResolved, onClarificationResolved]);
  const inProfile = view.kind === "profile";
  const sessionKey = `${view.profile}:${view.sessionId ?? "new"}`;
  const [modelOverride, setModelOverride] = useState(null);
  const [refreshBeat, setRefreshBeat] = useState(0);
  const [stopping, setStopping] = useState(false);
  const readAloudMountedRef = useRef(false);
  const readAloudStateRef = useRef(null);

  useEffect(() => {
    setModelOverride(null);
  }, [connectionId, sessionKey, activeProfile?.model]);

  useEffect(() => {
    setStopping(false);
  }, [pendingTurn?.requestId, pendingTurn?.ended]);

  const handleCancel = useCallback(() => {
    setStopping(true);
    onCancel?.();
  }, [onCancel]);
  const cancellableTurn = !!pendingTurn && !pendingTurn.settling && !pendingTurn.ended;

  // Lazy heavy fields — voice_id / models / mcps. Scoped per connection so two daemons with the same profile name never share state.
  const { detail: activeDetail, refresh: refreshActiveDetail } = useProfileDetail(connectionId ?? null, activeProfile?.name ?? null);
  const activeModels = activeProfile?.models ?? activeDetail?.models ?? [];

  // Let chat images resolve from the active profile's workspace (project assets), not just ~/.alpi.
  useEffect(() => {
    setImageRoots([activeDetail?.workspace]);
  }, [activeDetail?.workspace]);

  const serverAutoRead = !!activeDetail?.voice_auto_read;
  // members can't set the profile-global flag, so their toggle is a per-device pref keyed by connection+profile.
  const autoReadKey = `alpi:autoread:${connectionId ?? "local"}:${activeProfile?.name ?? ""}`;
  const [memberAutoRead, setMemberAutoRead] = useState(false);
  useEffect(() => {
    try { setMemberAutoRead(localStorage.getItem(autoReadKey) === "1"); } catch { setMemberAutoRead(false); }
  }, [autoReadKey]);
  const autoRead = canManageProfileSurfaces ? serverAutoRead : memberAutoRead;
  const ttsVoiceId = activeProfile?.voice_id ?? activeDetail?.voice_id ?? null;
  readAloudStateRef.current = {
    view,
    turns: sessionData?.turns ?? [],
    turnsOffset: sessionData?.turnsOffset,
    name: activeProfile?.name,
    voice: ttsVoiceId,
  };
  useEffect(() => {
    if (!readAloudMountedRef.current) {
      readAloudMountedRef.current = true;
      return;
    }
    if (readAloudTick <= 0) return;
    const { view, turns, turnsOffset, name, voice } = readAloudStateRef.current;
    if (view.kind !== "profile") return;
    const turnBase = Number.isInteger(turnsOffset) ? turnsOffset : 0;
    if (currentlyPlayingKey()) {
      stopTts();
      return;
    }
    for (let i = turns.length - 1; i >= 0; i--) {
      const text = turns[i]?.assistant;
      if (!text) continue;
      const key = `chat:${name}:${view.sessionId ?? "new"}:${turnBase + i}`;
      playTts({
        key,
        profile: name,
        voice: voice || VOICE_POOL[0],
        text,
      });
      break;
    }
  }, [readAloudTick]);
  const prevPendingRef = useRef(false);
  const lastPreviewRef = useRef("");
  // fire only on the pendingTurn truthy→null edge, never on history load
  useEffect(() => {
    if (pendingTurn?.assistantPreview) lastPreviewRef.current = pendingTurn.assistantPreview;
    const was = prevPendingRef.current;
    const now = !!pendingTurn;
    prevPendingRef.current = now;
    if (!(was && !now)) return;
    const turns = sessionData?.turns ?? [];
    const { speak, nextStreamed } = consumeAutoRead(lastPreviewRef.current, autoRead, turns);
    lastPreviewRef.current = nextStreamed;
    if (speak) {
      const idx = (sessionData?.turnsOffset ?? 0) + turns.length - 1;
      enqueueTts({
        key: `chat:${activeProfile?.name}:${view.sessionId ?? "new"}:${idx}`,
        profile: activeProfile?.name,
        voice: ttsVoiceId || VOICE_POOL[0],
        text: speak,
        accent: activeProfile?.accent,
      });
    }
  }, [pendingTurn, autoRead, sessionData, ttsVoiceId, activeProfile?.name, view.sessionId]);

  const noModel = !!activeProfile && !activeProfile.model;
  // Pre-split: needed full provider lists from summary to decide "is the profile chat-ready?". Post-split: the daemon precomputes `has_any_provider` so we don't drag the heavy detail down the hot poll.
  const hasProviders =
    !!activeProfile &&
    (typeof activeProfile.has_any_provider === "boolean"
      ? activeProfile.has_any_provider
      : (activeProfile.models?.length ?? 0) > 0
        || (activeProfile.provider_ollama?.length ?? 0) > 0);

  const paused = !!activeProfile?.paused;
  const syncVisible = useDelayedFlag(!!sessionSync);
  const notify = useNotify();
  const onTogglePause =
    onTogglePauseProfile && activeProfile ? () => onTogglePauseProfile(activeProfile) : null;
  const effectiveModel = pickEffectiveModel(modelOverride, activeProfile?.model);
  const contextWindow = useContextWindow(activeProfile?.name, effectiveModel, connectionId);
  const liveCtxTokens = pendingTurn?.ctxTokens ?? null;

  if (noModel) {
    return (
      <>
        {inProfile && activeProfile && (
          <ProfileChatHeader
            profile={activeProfile}
            sessionData={sessionData}
            model={effectiveModel}
            contextWindow={contextWindow}
            activeSessionId={view.sessionId}
            connectionId={connectionId}
            onOpenSettings={onConfigureProfile ? () => onConfigureProfile(activeProfile) : null}
            onRefresh={() => {
              setRefreshBeat((b) => b + 1);
              onRefreshSession?.();
            }}
            onOpenSkills={onOpenSkills}
            onOpenMemory={onOpenMemory}
            onOpenTools={onOpenTools}
            onOpenSchedule={onOpenSchedule}
            onNewSession={onNewSession}
            onChangeSession={onChangeSession}
            sessionsOpenTick={sessionsOpenTick}
          />
        )}
        <div className={styles.emptyShell}>
          <div className={styles.emptyContent}>
            <div className={styles.emptyMark}>
              <Fold fold={activeProfile?.fold} color={activeProfile?.accent || "var(--ink-3)"} size={FOLD_SIZES.hero} />
            </div>
            <div className={styles.titleGroup}>
              <h1 className={styles.emptyHeading}>
                {hasProviders
                  ? `@${profileLabel(activeProfile.name)} needs a model`
                  : `@${profileLabel(activeProfile.name)} needs a provider`}
              </h1>
              <p className={styles.emptyHint}>
                {onConfigureProfile
                  ? hasProviders
                    ? "Pick from one of the providers you've already connected."
                    : "Add an LLM provider (cloud or local Ollama) to start chatting."
                  : "Ask the host admin to finish setting up this profile."}
              </p>
            </div>
            {onConfigureProfile && (
              <Button
                variant="primary"
                size="hero"
                onClick={() => onConfigureProfile(activeProfile)}
              >
                {hasProviders ? "Pick a model" : "Set up provider"}
              </Button>
            )}
            <InlineRequests inline={inline} />
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      {inProfile && activeProfile && (
        <ProfileChatHeader
          profile={activeProfile}
          sessionData={sessionData}
          model={effectiveModel}
          contextWindow={contextWindow}
          liveCtxTokens={liveCtxTokens}
          activeSessionId={view.sessionId}
          connectionId={connectionId}
          onOpenSettings={onConfigureProfile ? () => onConfigureProfile(activeProfile) : null}
          onRefresh={() => {
            setRefreshBeat((b) => b + 1);
            onRefreshSession?.();
          }}
          onOpenSkills={onOpenSkills}
          onOpenMemory={onOpenMemory}
          onOpenTools={onOpenTools}
          onOpenSchedule={onOpenSchedule}
          onNewSession={onNewSession}
          onChangeSession={onChangeSession}
          sessionsOpenTick={sessionsOpenTick}
          paused={paused}
          onTogglePause={onTogglePause}
          autoRead={autoRead}
          onToggleAutoRead={activeProfile ? () => {
            if (autoRead) clearTtsQueue();
            if (canManageProfileSurfaces) {
              invoke("voice_set_auto_read", { profile: activeProfile.name, enabled: !autoRead })
                .then(() => refreshActiveDetail())
                .catch((e) => notify({ message: `auto-read toggle failed: ${e}`, variant: "error" }));
            } else {
              const next = !memberAutoRead;
              setMemberAutoRead(next);
              try { localStorage.setItem(autoReadKey, next ? "1" : "0"); } catch { /* */ }
            }
          } : null}
        />
      )}
      {paused && (
        <Banner kind="warning">
          <strong>This profile is paused.</strong> You can read the history; resume from the header to chat.
        </Banner>
      )}
      <div className={styles.body}>
        <RefreshBar
          key={syncVisible ? "sync" : refreshBeat}
          active={refreshBeat > 0 || syncVisible}
          controlled={syncVisible}
          accent={activeProfile?.accent ?? null}
          label={syncVisible ? "syncing conversation" : null}
        />
        <SessionView
          data={sessionData}
          connectionId={connectionId}
          profiles={profiles}
          pendingTurn={pendingTurn}
          accent={activeProfile?.accent ?? null}
          fold={activeProfile?.fold}
          showEmptyHint={inProfile && view.sessionId == null && !pendingTurn}
          profileName={activeProfile?.name ?? null}
          profileModel={activeProfile?.model ?? null}
          voiceId={activeProfile?.voice_id ?? activeDetail?.voice_id ?? null}
          onRewriteMessage={paused ? null : onRewriteMessage}
          onRetryMessage={paused ? null : onRetryMessage}
          onRefreshSession={onRefreshSession}
          sessionId={view.sessionId ?? null}
          rewriteDraft={rewriteDraft}
          searchOpen={searchOpen}
          onCloseSearch={onCloseSearch}
          loadError={loadError}
          onRetryLoad={onRetryLoad}
          inline={inline}
        />
      </div>
      <ChatComposer
        profiles={profiles}
        activeProfile={activeProfile}
        connectionId={connectionId}
        availableModels={activeModels}
        onConfigureProfile={onConfigureProfile}
        onSend={onSend}
        onCancel={cancellableTurn ? handleCancel : null}
        stopping={stopping}
        disabled={daemonOffline || paused}
        daemonOffline={daemonOffline}
        paused={paused}
        modelOverride={modelOverride}
        onModelChange={setModelOverride}
        rewriteDraft={rewriteDraft}
        onRewriteDraftApplied={onRewriteDraftApplied}
        pendingAttachment={pendingAttachment}
        onPendingAttachmentApplied={onPendingAttachmentApplied}
        minHeight={40}
      />
    </>
  );
}

function SessionView({
  data,
  connectionId,
  profiles,
  pendingTurn,
  accent,
  fold,
  showEmptyHint,
  profileName,
  profileModel,
  voiceId,
  onRewriteMessage,
  onRetryMessage,
  onRefreshSession,
  sessionId,
  rewriteDraft,
  searchOpen,
  onCloseSearch,
  loadError,
  onRetryLoad,
  inline,
}) {
  return (
    <>
      <Transcript
        data={data}
        connectionId={connectionId}
        profiles={profiles}
        pendingTurn={pendingTurn}
        accent={accent}
        fold={fold}
        showEmptyHint={showEmptyHint}
        profileName={profileName}
        profileModel={profileModel}
        voiceId={voiceId}
        onRewriteMessage={onRewriteMessage}
        onRetryMessage={onRetryMessage}
        onRefreshSession={onRefreshSession}
        sessionId={sessionId}
        rewriteDraft={rewriteDraft}
        searchOpen={searchOpen}
        onCloseSearch={onCloseSearch}
        loadError={loadError}
        onRetryLoad={onRetryLoad}
        inline={inline}
      />
    </>
  );
}

const Transcript = memo(function Transcript({
  data,
  connectionId,
  profiles,
  pendingTurn,
  accent,
  fold,
  showEmptyHint,
  profileName,
  profileModel,
  voiceId,
  onRewriteMessage,
  onRetryMessage,
  onRefreshSession,
  sessionId,
  rewriteDraft,
  searchOpen,
  onCloseSearch,
  loadError = null,
  onRetryLoad,
  inline = null,
}) {
  const allTurns = data?.turns ?? [];
  // session model, not current profile default: a model swap must not repaint history as routed
  const baseModel = data?.model || profileModel || null;
  const turnBase = Number.isInteger(data?.turnsOffset) ? data.turnsOffset : 0;
  const cut = rewriteCut({ pendingTurn, rewriteDraft, profileName, sessionId });
  const cutTurns = cut != null ? allTurns.slice(0, Math.max(0, cut - turnBase)) : allTurns;
  const turns = dropInflightStub(cutTurns, pendingTurn);
  const lastTurnInFlight = isLastTurnInFlight(turns, data?.in_flight);
  const liveTail = useSidecarTail({
    profile: profileName,
    sessionId,
    connectionId,
    active: lastTurnInFlight && !pendingTurn,
    onDone: onRefreshSession,
  });
  const stub = lastTurnInFlight && !pendingTurn ? turns[turns.length - 1] : null;
  const tailTurn = liveTail && stub && ((liveTail.tools?.length ?? 0) > 0 || liveTail.assistant || liveTail.reasoning)
    ? {
        user: stub.user,
        at: stub.at,
        attachments: stub.attachments,
        tools: liveTail.tools,
        assistantPreview: liveTail.assistant,
        reasoningPreview: liveTail.reasoning,
        reasoned_s: liveTail.reasonedSeconds ?? undefined,
        reasoningDone: liveTail.reasoningDone,
      }
    : null;
  const renderTurns = tailTurn ? turns.slice(0, -1) : turns;
  const streamingTurn = pendingTurn ?? tailTurn;
  const fresh = useFreshTurns(
    `${connectionId ?? "local"}:${profileName}:${sessionId ?? "new"}`,
    renderTurns.map((t, i) => t.at ?? turnBase + i),
    { ready: data != null || showEmptyHint, streamKey: pendingTurn?.requestId ?? null },
  );
  const inlineBlock = <InlineRequests inline={inline} />;

  const scrollRef = useStickyScroll([data, pendingTurn, tailTurn, inline], streamingTurn?.requestId ?? (tailTurn ? `tail:${sessionId}` : null));
  const { farFromBottom, scrollToBottom } = useScrollProgress(scrollRef);
  const search = useTranscriptSearch(scrollRef, searchOpen);
  const closeSearch = () => {
    search.reset();
    onCloseSearch?.();
  };
  useScrollAnchor(scrollRef, turnBase, `${profileName}:${sessionId ?? "new"}`);

  const [showSkeleton, setShowSkeleton] = useState(false);
  useEffect(() => {
    setShowSkeleton(false);
    const t = setTimeout(() => setShowSkeleton(true), 450);
    return () => clearTimeout(t);
  }, [profileName, sessionId]);

  if (showEmptyHint) {
    return (
      <div className={styles.empty}>
        <Fold fold={fold} color={accent || "var(--accent)"} size={FOLD_SIZES.hero} />
        <div className={styles.emptyHeading}>Start a new thread</div>
        {profileModel && (
          <div className={styles.emptyModel}>{profileModel}</div>
        )}
        {inlineBlock}
      </div>
    );
  }

  if (turns.length === 0 && !data && !pendingTurn) {
    if (loadError) {
      return (
        <div className={styles.loading}>
          <LoadFailed label="this conversation" error={loadError} onRetry={onRetryLoad} />
          {inlineBlock}
        </div>
      );
    }
    if (!showSkeleton) return <div className={styles.loading}>{inlineBlock}</div>;
    return (
      <div className={styles.loading}>
        <ChatLoadSkeleton />
        {inlineBlock}
      </div>
    );
  }

  return (
    <>
      {searchOpen && (
        <SearchBar
          query={search.query}
          setQuery={search.setQuery}
          total={search.total}
          currentIndex={search.currentIndex}
          onNext={search.next}
          onPrev={search.prev}
          onClose={closeSearch}
        />
      )}
      <div className={styles.transcriptWrap}>
        <div ref={scrollRef} className={styles.transcript}>
          <div className={styles.timeline}>
            <HistoryTurns
              turns={renderTurns}
              turnBase={turnBase}
              connectionId={connectionId}
              baseModel={baseModel}
              profiles={profiles}
              accent={accent}
              fold={fold}
              profileName={profileName}
              voiceId={voiceId}
              onRewriteMessage={onRewriteMessage}
              onRetryMessage={onRetryMessage}
              sessionId={sessionId}
              lastTurnInFlight={lastTurnInFlight && !tailTurn}
              freshKeys={fresh.freshKeys}
            />
            {streamingTurn ? (
              <PendingTurn
                turn={streamingTurn}
                accent={accent}
                fold={fold}
                profiles={profiles}
                fresh={fresh.streamFresh}
                inline={inlineBlock}
              />
            ) : inlineBlock}
          </div>
        </div>
        <JumpToLatest show={farFromBottom} onClick={scrollToBottom} />
      </div>
    </>
  );
});

const HistoryTurns = memo(function HistoryTurns({
  turns,
  turnBase = 0,
  connectionId,
  baseModel,
  profiles,
  accent,
  fold,
  profileName,
  voiceId,
  onRewriteMessage,
  onRetryMessage,
  sessionId,
  lastTurnInFlight,
  freshKeys,
}) {
  return (
    <>
      {turns.map((t, i) => (
        <Turn
          key={t.at ?? turnBase + i}
          fresh={freshKeys?.get(t.at ?? turnBase + i) === true}
          turn={t}
          connectionId={connectionId}
          baseModel={baseModel}
          profiles={profiles}
          accent={accent}
          fold={fold}
          profileName={profileName}
          voiceId={voiceId}
          sessionId={sessionId}
          turnIndex={turnBase + i}
          onRewriteMessage={onRewriteMessage}
          onRetryMessage={onRetryMessage}
          inFlight={lastTurnInFlight && i === turns.length - 1}
        />
      ))}
    </>
  );
});

const Turn = memo(function Turn({
  turn,
  connectionId,
  baseModel,
  profiles,
  accent,
  fold,
  profileName,
  voiceId,
  sessionId,
  turnIndex,
  onRewriteMessage,
  onRetryMessage,
  inFlight = false,
  fresh = false,
}) {
  const notify = useNotify();
  const allTools = turn.tools ?? [];
  const parts = turnParts(turn);
  const process = useMemo(
    () => processTimeline(
      (turn.tools ?? []).map((t) => compactProducedTool(t, turn.output_attachments)),
      turn.reasoning,
      parts.reasonedSeconds,
      turn.reasoning_spans,
      { mergeUnattributed: true },
    ),
    [turn.tools, turn.output_attachments, turn.reasoning, parts.reasonedSeconds, turn.reasoning_spans],
  );
  const peerTool = peerReplyFrom(allTools);
  const lastAskUserAnswer = parts.askUsers[parts.askUsers.length - 1]?.result;
  // Only suppress the assistant message when it is the *exact* echo of the
  // ask_user result. If the model adds genuine commentary after a cancel /
  // timeout / no-handler (e.g. "no problem, defaulting to X"), keep it.
  const hideAssistant = lastAskUserAnswer && turn.assistant?.trim() === lastAskUserAnswer;
  const [ttsState, setTtsState] = useState(null);
  useEffect(() => subscribeTts(setTtsState), []);
  const online = useOnline();
  const ttsKey = `chat:${profileName}:${sessionId ?? "new"}:${turnIndex}`;
  const ttsKind = ttsState?.key === ttsKey ? ttsState.kind : null;
  const isLoading = ttsKind === "loading";
  const isPlaying = ttsKind === "playing";
  const ttsDisabled = !online && !isPlaying;
  const speakTip = !online && !isPlaying
    ? "Offline — TTS unavailable"
    : isLoading ? "Loading…" : isPlaying ? "Stop" : "Read aloud";
  const onSpeak = () => {
    if (!turn.assistant) return;
    playTts({
      key: ttsKey,
      profile: profileName,
      voice: voiceId || VOICE_POOL[0],
      text: turn.assistant,
    });
  };
  const copyMessage = async (text) => {
    if (await copyText(text)) notify({ message: "Message copied", variant: "success" });
    else notify({ message: "Copy failed", variant: "error" });
  };
  return (
    <div className={`${styles.turn} ${fresh ? styles.turnEnter : ""}`} data-enter={fresh ? "" : undefined}>
      {turn.user && (
        <ProfileMessage
          role="user"
          footer={
            <TurnFooter ts={turn.at} side="right">
              {onRewriteMessage && (
                <Tip text="Edit message" side="up">
                  <IconBtn
                    aria-label="Edit message"
                    onClick={() =>
                      onRewriteMessage(profileName, sessionId, turnIndex, turn.user)
                    }
                    className={styles.userActionBtn}
                  >
                    <EditIcon style={{ width: 12, height: 12 }} />
                  </IconBtn>
                </Tip>
              )}
              <Tip text="Copy" side="up">
                <IconBtn
                  aria-label="Copy message"
                  onClick={() => copyMessage(turn.user)}
                  className={styles.userActionBtn}
                >
                  <DSCopyIcon style={{ width: 12, height: 12 }} />
                </IconBtn>
              </Tip>
            </TurnFooter>
          }
        >
          {turn.attachments?.length > 0 && (
            <AttachmentChips items={turn.attachments} variant="message" />
          )}
          <Markdown as="div" source={turn.user} className="alpi-md" />
        </ProfileMessage>
      )}
      {(process.length > 0 || parts.askUsers.length > 0) && (
        <div className={styles.steps}>
          {process.length > 0 && <ProcessBlock entries={process} accent={accent} fold={fold} />}
          {parts.askUsers.map((a, i) => (
            <AskUserAnswer key={`a-${a.tool_id ?? i}`} result={a.result} question={a.question} accent={accent} fold={fold} />
          ))}
        </div>
      )}
      {turn.assistant && !hideAssistant && peerTool && (
        <PeerReplyCard
          peerId={peerTool.args?.peer_id || "peer"}
          reply={turn.assistant}
          accent={accentForPeer(peerTool.args?.peer_id, profiles)}
          fold={(profiles || []).find((p) => p.name === peerTool.args?.peer_id)?.fold}
        />
      )}
      {(turn.assistant || turn.output_attachments?.length > 0) && !hideAssistant && !peerTool && (
        <ProfileMessage
          role="assistant"
          footer={
            <TurnFooter ts={turn.ended_at || turn.at} meta={turnMeta(turn, baseModel)} side="left">
              <Tip text="Copy response" side="up">
                <IconBtn
                  aria-label="Copy response"
                  onClick={() => copyMessage(turn.assistant)}
                  className={styles.agentActionBtn}
                >
                  <DSCopyIcon style={{ width: 13, height: 13 }} />
                </IconBtn>
              </Tip>
              {onRetryMessage && turn.user && (
                <Tip text="Retry from here" side="up">
                  <IconBtn
                    aria-label="Retry from here"
                    onClick={() =>
                      onRetryMessage(profileName, sessionId, turnIndex, turn.user)
                    }
                    className={styles.agentActionBtn}
                  >
                    <RefreshIcon style={{ width: 13, height: 13 }} />
                  </IconBtn>
                </Tip>
              )}
              <Tip text={speakTip} side="up">
                <IconBtn
                  aria-label={speakTip}
                  disabled={ttsDisabled}
                  onClick={onSpeak}
                  className={styles.agentActionBtn}
                >
                  {isLoading ? (
                    <DSSpinnerIcon style={{ width: 13, height: 13 }} />
                  ) : isPlaying ? (
                    <StopIcon style={{ width: 13, height: 13 }} />
                  ) : (
                    <VolumeIcon style={{ width: 13, height: 13 }} />
                  )}
                </IconBtn>
              </Tip>
            </TurnFooter>
          }
        >
          <Markdown
            as="div"
            source={stripProducedImageMarkdown(turn.assistant, turn.output_attachments)}
            className="alpi-md"
          />
          {imageProduced(turn.output_attachments).length > 0 && (
            <ProducedImages images={imageProduced(turn.output_attachments)} />
          )}
          {nonImageProduced(turn.output_attachments).length > 0 && (
            <AttachmentChips
              items={nonImageProduced(turn.output_attachments)}
              variant="message"
              profile={profileName}
              connectionId={connectionId}
            />
          )}
        </ProfileMessage>
      )}
      {turn.unfinished && (
        <div className={styles.unfinished}>Interrupted before final reply</div>
      )}
      {!turn.unfinished && inFlight && (
        <div className={styles.unfinished}>Still working…</div>
      )}
    </div>
  );
});

const ASK_USER_NO_ANSWER_TAGS = [
  ["User cancelled clarification.", "CANCELLED"],
  ["No response received", "EXPIRED"],
  ["This run has no live user", "NO ANSWER"],
  ["No user-facing surface accepted", "NO ANSWER"],
  ["Clarification handler failed", "FAILED"],
];

function askUserNoAnswerTag(result) {
  if (!result) return null;
  for (const [prefix, tag] of ASK_USER_NO_ANSWER_TAGS) {
    if (result.startsWith(prefix)) return tag;
  }
  return null;
}

function AskUserAnswer({ result, question, accent, fold }) {
  const noAnswerTag = askUserNoAnswerTag(result);
  if (noAnswerTag) {
    return (
      <div className={styles.askUserBanner}>
        <div className={styles.askUserBannerQuestion}>{question || result}</div>
        <div className={styles.askUserBannerTag}>
          <span aria-hidden>∅</span>
          <span>{noAnswerTag}</span>
        </div>
      </div>
    );
  }
  return (
    <div className={styles.askUserAnswer}>
      <Fold fold={fold} color={accent || undefined} className={styles.askUserFold} />
      <span className={styles.askUserAnswerLabel}>{result}</span>
    </div>
  );
}

function accentForPeer(peerId, profiles) {
  const known = (profiles || []).find((p) => p.name === peerId);
  if (known?.accent) return known.accent;
  let h = 0;
  const s = peerId || "";
  for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) | 0;
  return ACCENT_HEXES[Math.abs(h) % ACCENT_HEXES.length];
}

function peerReplyFrom(tools) {
  const list = Array.isArray(tools) ? tools : [];
  for (let i = list.length - 1; i >= 0; i -= 1) {
    const t = list[i];
    if (t.ok === false) continue;
    if (t.ok == null) return null;
    return t.name === "peer" ? t : null;
  }
  return null;
}

function PeerReplyCard({ peerId, reply, accent, fold }) {
  const tint = accent || "var(--accent)";
  const meta = (
    <span className={styles.peerMeta}>
      <Fold fold={fold} color={tint} />
      <span className={styles.peerName}>@{peerId}</span>
    </span>
  );
  return (
    <MessageBubble side="left" tint={tint} meta={meta}>
      <Markdown as="div" source={reply} className="alpi-md" />
    </MessageBubble>
  );
}

function InlineRequests({ inline }) {
  const approval = inline?.approvals?.[0] ?? null;
  const clarification = inline?.clarifications?.[0] ?? null;
  if (!approval && !clarification) return null;
  return (
    <div className={styles.inline}>
      {approval && <InlineApproval request={approval} onResolved={inline.onApprovalResolved} />}
      {clarification && <InlineClarification request={clarification} onResolved={inline.onClarificationResolved} />}
    </div>
  );
}

function TurnFooter({ ts, meta = null, side = "left", children }) {
  const time = (
    <Mono className={`tnum ${styles.footTime}`}>
      <RelativeTime ts={ts} />
    </Mono>
  );
  return (
    <div className={styles.foot}>
      {meta ? <Tip text={meta} side={side === "right" ? "up-r" : "up-l"}>{time}</Tip> : time}
      <span className={styles.footActions}>{children}</span>
    </div>
  );
}

function turnMeta(turn, baseModel) {
  const usage = [
    turn.tokens != null ? `${(turn.tokens / 1000).toFixed(1)}K tokens` : null,
    turn.cost != null ? `$${turn.cost.toFixed(4)}` : null,
  ].filter(Boolean).join(" · ");
  const model = turn.model || baseModel || null;
  const routed = turn.model && baseModel && turn.model !== baseModel ? turn.model : null;
  const took = turn.ended_at && turn.at && turn.ended_at > turn.at ? fmtDuration(turn.ended_at - turn.at) : "";
  if (!usage && !model && !took) return null;
  return (
    <span className={styles.meta}>
      {usage && <span>{usage}</span>}
      {(model || took) && (
        <span className={styles.metaModel}>
          {model && <span title={routed ? `Ran on ${routed}` : undefined}>{model.split("/").pop()}</span>}
          {model && took && " · "}
          {took}
        </span>
      )}
    </span>
  );
}

function PendingTurn({ turn, accent, fold, profiles, fresh = false, inline = null }) {
  const allTools = turn.tools ?? [];
  const parts = turnParts({
    tools: allTools,
    reasoning: turn.reasoningPreview,
    reasoned_s: turn.reasoned_s,
  });
  const answered = !!turn.assistantPreview;
  const runningTool = allTools.some((t) => t.ok == null);
  const closed = !!turn.error || !!turn.ended || !!turn.settling;
  const thinking = !answered && !runningTool && !turn.reasoningDone && !closed;
  const process = processTimeline(
    allTools.map((t) => compactProducedTool(t, turn.output_attachments)),
    turn.reasoningPreview,
    parts.reasonedSeconds,
  );
  const peerTool = peerReplyFrom(allTools);
  return (
    <div className={`${styles.turn} ${fresh ? styles.turnEnter : ""}`} data-enter={fresh ? "" : undefined}>
      {turn.user && (
        <ProfileMessage role="user">
          {turn.attachments?.length > 0 && (
            <AttachmentChips items={turn.attachments} variant="message" />
          )}
          <Markdown as="div" source={turn.user} className="alpi-md" />
        </ProfileMessage>
      )}
      {(process.length > 0 || parts.askUsers.length > 0 || thinking) && (
        <div className={styles.steps}>
          {(process.length > 0 || thinking) && (
            <ProcessBlock entries={process} accent={accent} fold={fold} thinking={thinking} answered={answered} />
          )}
          {parts.askUsers.map((a, i) => (
            <AskUserAnswer key={`a-${a.tool_id ?? i}`} result={a.result} question={a.question} accent={accent} fold={fold} />
          ))}
        </div>
      )}
      {turn.assistantPreview && peerTool && (
        <PeerReplyCard
          peerId={peerTool.args?.peer_id || "peer"}
          reply={turn.assistantPreview}
          accent={accentForPeer(peerTool.args?.peer_id, profiles)}
          fold={(profiles || []).find((p) => p.name === peerTool.args?.peer_id)?.fold}
        />
      )}
      {turn.assistantPreview && !peerTool && (
        <ProfileMessage role="assistant">
          <StreamingMarkdown source={turn.assistantPreview} />
        </ProfileMessage>
      )}
      {turn.error && (
        <div className={styles.toolError}>{turn.error}</div>
      )}
      {inline}
    </div>
  );
}
