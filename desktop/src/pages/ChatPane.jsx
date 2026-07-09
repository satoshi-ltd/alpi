import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Reasoning from "../primitives/Reasoning.jsx";
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
import { relativeTime } from "../lib/time.js";
import { reasoningSteps } from "../lib/reasoningSteps.js";
import { profileLabel } from "../lib/profile-display.js";
import { ChatLoadSkeleton } from "./ChatSkeletons.jsx";
import SearchBar from "../primitives/SearchBar.jsx";
import { useTranscriptSearch } from "../hooks/useTranscriptSearch.js";
import { useContextWindow } from "../hooks/useContextWindow.js";
import { useNotify } from "../primitives/Notification.jsx";
import Logo from "../primitives/Logo.jsx";
import Markdown from "../primitives/Markdown.jsx";
import { ACCENT_SWATCHES } from "../primitives/SettingsLayout.jsx";
import ProducedImages from "../primitives/ProducedImages.jsx";
import { setImageRoots } from "../lib/imageRoots.js";
import { Banner, JumpToLatest, MessageBubble, NewChatHero, ProfileChatHeader } from "../primitives/index.js";
import { ProfileMessage } from "../primitives/index.js";
import {
  AlpiSilhouette,
  CopyIcon as DSCopyIcon,
  Diamond,
  EditIcon,
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
import { playTts, subscribeTts, enqueueTts, VOICE_POOL } from "../lib/tts.js";
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
  onSelectProfile,
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
  onNewSession,
  onChangeSession,
  onRefreshSession,
  daemonOffline = false,
  searchOpen = false,
  onCloseSearch,
  recents = [],
  onOpenRecent,
}) {
  const inProfile = view.kind === "profile";
  const inEmpty = !pendingTurn && view.kind === "empty";
  const sessionKey = inProfile ? `${view.profile}:${view.sessionId ?? "new"}` : "empty";
  const [modelOverride, setModelOverride] = useState(null);
  const [refreshBeat, setRefreshBeat] = useState(0);
  const [stopping, setStopping] = useState(false);

  useEffect(() => {
    setModelOverride(null);
  }, [connectionId, sessionKey, activeProfile?.model]);

  useEffect(() => {
    setStopping(false);
  }, [pendingTurn?.requestId]);

  const handleCancel = useCallback(() => {
    setStopping(true);
    onCancel?.();
  }, [onCancel]);

  // Lazy heavy fields — voice_id / models / mcps. Scoped per connection so two daemons with the same profile name never share state.
  const { detail: activeDetail, refresh: refreshActiveDetail } = useProfileDetail(connectionId ?? null, activeProfile?.name ?? null);
  const activeModels = activeProfile?.models ?? activeDetail?.models ?? [];

  // Let chat images resolve from the active profile's workspace (project assets), not just ~/.alpi.
  useEffect(() => {
    setImageRoots([activeDetail?.workspace]);
  }, [activeDetail?.workspace]);

  const autoRead = !!activeDetail?.voice_auto_read;
  const ttsVoiceId = activeProfile?.voice_id ?? activeDetail?.voice_id ?? null;
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
  const onTogglePause =
    onTogglePauseProfile && activeProfile ? () => onTogglePauseProfile(activeProfile) : null;
  const effectiveModel = pickEffectiveModel(modelOverride, sessionData?.model, activeProfile?.model);
  const contextWindow = useContextWindow(activeProfile?.name, effectiveModel, connectionId);

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
            onOpenSettings={onConfigureProfile ? () => onConfigureProfile(activeProfile) : null}
            onRefresh={() => {
              setRefreshBeat((b) => b + 1);
              onRefreshSession?.();
            }}
            onOpenSkills={onOpenSkills}
            onOpenMemory={onOpenMemory}
            onOpenTools={onOpenTools}
            onNewSession={onNewSession}
            onChangeSession={onChangeSession}
          />
        )}
        <div className={styles.emptyShell}>
          <div className={styles.emptyContent}>
            <div className={styles.emptyMark}>
              <Logo color={activeProfile?.accent || "var(--ink)"} />
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
          </div>
        </div>
      </>
    );
  }

  if (inEmpty) {
    return (
      <NewChatHero
        profiles={profiles}
        recents={recents}
        onOpenRecent={onOpenRecent}
        accent={activeProfile?.accent}
      >
        <ChatComposer
          profiles={profiles}
          activeProfile={activeProfile}
          connectionId={connectionId}
          availableModels={activeModels}
          onSelectProfile={onSelectProfile}
          onConfigureProfile={onConfigureProfile}
          onSend={onSend}
          onCancel={pendingTurn ? handleCancel : null}
          stopping={stopping}
          disabled={daemonOffline || paused}
          daemonOffline={daemonOffline}
          paused={paused}
          showPicker={view.kind === "empty"}
          modelOverride={modelOverride}
          onModelChange={setModelOverride}
          embedded
          rewriteDraft={rewriteDraft}
          onRewriteDraftApplied={onRewriteDraftApplied}
          pendingAttachment={pendingAttachment}
          onPendingAttachmentApplied={onPendingAttachmentApplied}
          minHeight={68}
        />
      </NewChatHero>
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
          activeSessionId={view.sessionId}
          onOpenSettings={onConfigureProfile ? () => onConfigureProfile(activeProfile) : null}
          onRefresh={() => {
            setRefreshBeat((b) => b + 1);
            onRefreshSession?.();
          }}
          onOpenSkills={onOpenSkills}
          onOpenMemory={onOpenMemory}
          onOpenTools={onOpenTools}
          onNewSession={onNewSession}
          onChangeSession={onChangeSession}
          paused={paused}
          onTogglePause={onTogglePause}
          autoRead={autoRead}
          onToggleAutoRead={activeProfile ? () => {
            invoke("voice_set_auto_read", { profile: activeProfile.name, enabled: !autoRead })
              .then(() => refreshActiveDetail())
              .catch(() => {});
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
          profiles={profiles}
          pendingTurn={pendingTurn}
          accent={activeProfile?.accent ?? null}
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
        />
      </div>
      <ChatComposer
        profiles={profiles}
        activeProfile={activeProfile}
        connectionId={connectionId}
        availableModels={activeModels}
        onSelectProfile={onSelectProfile}
        onConfigureProfile={onConfigureProfile}
        onSend={onSend}
        onCancel={pendingTurn ? handleCancel : null}
        stopping={stopping}
        disabled={daemonOffline || paused}
        daemonOffline={daemonOffline}
        paused={paused}
        showPicker={false}
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
  profiles,
  pendingTurn,
  accent,
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
}) {
  return (
    <>
      <Transcript
        data={data}
        profiles={profiles}
        pendingTurn={pendingTurn}
        accent={accent}
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
      />
    </>
  );
}

const Transcript = memo(function Transcript({
  data,
  profiles,
  pendingTurn,
  accent,
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
}) {
  const allTurns = data?.turns ?? [];
  const turnBase = Number.isInteger(data?.turnsOffset) ? data.turnsOffset : 0;
  const cut = rewriteCut({ pendingTurn, rewriteDraft, profileName, sessionId });
  const cutTurns = cut != null ? allTurns.slice(0, Math.max(0, cut - turnBase)) : allTurns;
  const turns = dropInflightStub(cutTurns, pendingTurn);
  const lastTurnInFlight = isLastTurnInFlight(turns, data?.in_flight);
  const liveTail = useSidecarTail({
    profile: profileName,
    sessionId,
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
      }
    : null;
  const renderTurns = tailTurn ? turns.slice(0, -1) : turns;
  const streamingTurn = pendingTurn ?? tailTurn;

  const scrollRef = useStickyScroll([data, pendingTurn, tailTurn], streamingTurn?.requestId ?? (tailTurn ? `tail:${sessionId}` : null));
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
        <AlpiSilhouette color={accent || "var(--accent)"} />
        <div className={styles.emptyHeading}>
          start a thread with {profileName}
        </div>
        {profileModel && (
          <div className={styles.emptyModel}>{profileModel}</div>
        )}
      </div>
    );
  }

  if (turns.length === 0 && !data && !pendingTurn) {
    if (!showSkeleton) return <div className={styles.loading} />;
    return (
      <div className={styles.loading}>
        <ChatLoadSkeleton />
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
              profiles={profiles}
              accent={accent}
              profileName={profileName}
              voiceId={voiceId}
              onRewriteMessage={onRewriteMessage}
              onRetryMessage={onRetryMessage}
              sessionId={sessionId}
              lastTurnInFlight={lastTurnInFlight && !tailTurn}
            />
            {streamingTurn && <PendingTurn turn={streamingTurn} accent={accent} profiles={profiles} />}
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
  profiles,
  accent,
  profileName,
  voiceId,
  onRewriteMessage,
  onRetryMessage,
  sessionId,
  lastTurnInFlight,
}) {
  return (
    <>
      {turns.map((t, i) => (
        <Turn
          key={t.at ?? turnBase + i}
          turn={t}
          profiles={profiles}
          accent={accent}
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
  profiles,
  accent,
  profileName,
  voiceId,
  sessionId,
  turnIndex,
  onRewriteMessage,
  onRetryMessage,
  inFlight = false,
}) {
  const notify = useNotify();
  const allTools = turn.tools ?? [];
  const steps = reasoningSteps(turn);
  const peerTool = peerReplyFrom(allTools);
  const askUserAnswers = allTools
    .filter((t) => t.name === "ask_user")
    .map((t) => ({
      tool_id: t.tool_id,
      result: (t.output || t.result || "").trim(),
      question: t.args?.question || "",
    }))
    .filter((a) => a.result);
  const lastAskUserAnswer = askUserAnswers[askUserAnswers.length - 1]?.result;
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
    <div className={styles.turn}>
      {turn.user && (
        <ProfileMessage
          role="user"
          accent={accent || "var(--accent)"}
          footer={
            <>
              <Mono className={`tnum ${styles.userActionTime}`}>
                {relativeTime(turn.at)}
              </Mono>
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
            </>
          }
        >
          {turn.attachments?.length > 0 && (
            <AttachmentChips items={turn.attachments} variant="message" />
          )}
          <Markdown as="div" source={turn.user} className="alpi-md" />
        </ProfileMessage>
      )}
      {steps.length > 0 && (
        <div className={styles.steps}>
          {steps.map((step, i) => {
            if (step.kind === "reasoning") {
              return <Reasoning key={`r-${i}`} text={step.text} seconds={step.seconds} />;
            }
            if (step.kind === "askUser") {
              return step.result ? (
                <AskUserAnswer key={`a-${i}`} result={step.result} question={step.question} accent={accent} />
              ) : null;
            }
            const tools = step.tools.map((t) => compactProducedTool(t, turn.output_attachments));
            return (
              <div key={`t-${i}`} className={styles.toolGroup}>
                {groupConsecutiveTools(tools).map((g, j) => (
                  <ToolGroupCard key={`g-${j}-${g.tools[0].tool_id ?? g.name}`} group={g} accent={accent} />
                ))}
              </div>
            );
          })}
        </div>
      )}
      {turn.assistant && !hideAssistant && peerTool && (
        <PeerReplyCard
          peerId={peerTool.args?.peer_id || "peer"}
          reply={turn.assistant}
          accent={accentForPeer(peerTool.args?.peer_id, profiles)}
        />
      )}
      {(turn.assistant || turn.output_attachments?.length > 0) && !hideAssistant && !peerTool && (
        <ProfileMessage
          role="assistant"
          footer={
            <>
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
              <span className={styles.agentMeta}>
                <Mono className="tnum">{relativeTime(turn.at)}</Mono>
                {turn.tokens != null && (
                  <>
                    <span className={styles.agentMetaSep}>·</span>
                    <Mono className="tnum">{(turn.tokens / 1000).toFixed(1)}K</Mono>
                  </>
                )}
                {turn.cost != null && (
                  <>
                    <span className={styles.agentMetaSep}>·</span>
                    <Mono className="tnum">${turn.cost.toFixed(4)}</Mono>
                  </>
                )}
              </span>
            </>
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
            <AttachmentChips items={nonImageProduced(turn.output_attachments)} variant="message" />
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

function AskUserAnswer({ result, question, accent }) {
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
      <Diamond color={accent || undefined} className={styles.askUserDiamond} />
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
  return ACCENT_SWATCHES[Math.abs(h) % ACCENT_SWATCHES.length];
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

function PeerReplyCard({ peerId, reply, accent }) {
  const tint = accent || "var(--accent)";
  const meta = (
    <span className={styles.peerMeta}>
      <Diamond color={tint} />
      <span className={styles.peerName}>@{peerId}</span>
    </span>
  );
  return (
    <MessageBubble side="left" tint={tint} meta={meta}>
      <Markdown as="div" source={reply} className="alpi-md" />
    </MessageBubble>
  );
}

function previewForArgs(args) {
  if (!args || typeof args !== "object") return "";
  return Object.entries(args).slice(0, 2).map(([k, v]) => {
    const raw = typeof v === "string" ? v : JSON.stringify(v);
    const compact = raw.length > 60 ? raw.slice(0, 60) + "…" : raw;
    return `${k}=${compact}`;
  }).join(" ");
}

function renderPreview(str) {
  const parts = String(str).split(/(\b\w+=)/);
  return parts.map((p, i) =>
    i % 2 === 1
      ? <span key={i} className={styles.toolPreviewKey}>{p}</span>
      : <span key={i} className={styles.toolPreviewVal}>{p}</span>
  );
}

// Adjacent same-name tools collapse into one row with ×N badge + per-call dots; click to expand.
function groupConsecutiveTools(tools) {
  const groups = [];
  for (const t of tools) {
    const last = groups[groups.length - 1];
    if (last && last.name === t.name) {
      last.tools.push(t);
    } else {
      groups.push({ name: t.name, tools: [t] });
    }
  }
  return groups;
}

function statusOf(t) {
  return t.ok === null || t.ok === undefined ? "running" : t.ok ? "ok" : "fail";
}

const ToolGroupCard = memo(function ToolGroupCard({ group, accent }) {
  const [expanded, setExpanded] = useState(false);
  if (group.tools.length === 1) {
    const t = group.tools[0];
    return (
      <ToolCard
        name={t.name}
        preview={previewForArgs(t.args)}
        ok={t.ok ?? null}
        accent={accent}
      />
    );
  }
  // Group derives its visual status from the worst child: any failed → fail; any running → running; else ok.
  const groupStatus = group.tools.some((t) => statusOf(t) === "fail")
    ? "fail"
    : group.tools.some((t) => statusOf(t) === "running")
      ? "running"
      : "ok";
  const diamondColor = groupStatus === "fail" ? "var(--c-danger)" : (accent || undefined);
  const rootStyle = groupStatus === "running" && accent ? { "--accent": accent } : undefined;
  const last = group.tools[group.tools.length - 1];
  return (
    <>
      <button
        type="button"
        className={`${styles.tool} ${styles[`tool_${groupStatus}`]} ${styles.toolGroupClickable}`}
        style={rootStyle}
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={expanded ? "Collapse tool group" : `Expand ${group.tools.length} ${group.name} calls`}
      >
        <Diamond color={diamondColor} className={styles.toolIcon} />
        <span className={styles.toolName}>{group.name}</span>
        <span className={styles.toolGroupBadge}>×{group.tools.length}</span>
        <span className={styles.toolGroupDots}>
          {group.tools.map((t, i) => (
            <span
              key={t.tool_id ?? i}
              className={`${styles.toolGroupDot} ${styles[`toolGroupDot_${statusOf(t)}`]}`}
            />
          ))}
        </span>
        {last.args ? (
          <span className={styles.toolPreview}>{renderPreview(previewForArgs(last.args))}</span>
        ) : null}
      </button>
      {expanded && group.tools.map((t, i) => (
        <div key={t.tool_id ?? `${t.name}:${i}`} className={styles.toolGroupChild}>
          <ToolCard
            name={t.name}
            preview={previewForArgs(t.args)}
            ok={t.ok ?? null}
            accent={accent}
          />
        </div>
      ))}
    </>
  );
});

function PendingTurn({ turn, accent, profiles }) {
  const allTools = turn.tools ?? [];
  const steps = reasoningSteps({
    at: turn.at,
    tools: allTools,
    reasoning: turn.reasoningPreview,
    reasoned_s: turn.reasoned_s,
  }, { active: !turn.assistantPreview });
  const peerTool = peerReplyFrom(allTools);
  return (
    <div className={styles.turn}>
      {turn.user && (
        <ProfileMessage role="user" accent={accent || "var(--accent)"}>
          {turn.attachments?.length > 0 && (
            <AttachmentChips items={turn.attachments} variant="message" />
          )}
          <Markdown as="div" source={turn.user} className="alpi-md" />
        </ProfileMessage>
      )}
      {steps.length > 0 && (
        <div className={styles.steps}>
          {steps.map((step, i) => {
            if (step.kind === "reasoning") {
              return <Reasoning key={`r-${i}`} text={step.text} seconds={step.seconds} streaming={step.trailing} />;
            }
            if (step.kind === "askUser") {
              return step.result ? (
                <AskUserAnswer key={`a-${i}`} result={step.result} question={step.question} accent={accent} />
              ) : null;
            }
            const tools = step.tools.map((t) => compactProducedTool(t, turn.output_attachments));
            return (
              <div key={`t-${i}`} className={styles.toolGroup}>
                {groupConsecutiveTools(tools).map((g, j) => (
                  <ToolGroupCard key={`g-${j}-${g.tools[0].tool_id ?? g.name}`} group={g} accent={accent} />
                ))}
              </div>
            );
          })}
        </div>
      )}
      {turn.assistantPreview && peerTool && (
        <PeerReplyCard
          peerId={peerTool.args?.peer_id || "peer"}
          reply={turn.assistantPreview}
          accent={accentForPeer(peerTool.args?.peer_id, profiles)}
        />
      )}
      {turn.assistantPreview && !peerTool && (
        <ProfileMessage role="assistant">
          <Markdown as="div" source={turn.assistantPreview} className="alpi-md" />
        </ProfileMessage>
      )}
      {turn.error && (
        <div className={styles.toolError}>{turn.error}</div>
      )}
    </div>
  );
}

const ToolCard = memo(function ToolCard({ name, preview, ok, accent }) {
  const status = ok === null ? "running" : ok ? "ok" : "fail";
  const diamondColor =
    status === "fail" ? "var(--c-danger)" : (accent || undefined);
  const rootStyle = status === "running" && accent
    ? { "--accent": accent }
    : undefined;
  return (
    <div
      className={`${styles.tool} ${styles[`tool_${status}`]}`}
      style={rootStyle}
    >
      <Diamond color={diamondColor} className={styles.toolIcon} />
      <span className={styles.toolName}>{name}</span>
      {preview && (
        <span className={styles.toolPreview}>{renderPreview(preview)}</span>
      )}
    </div>
  );
});
