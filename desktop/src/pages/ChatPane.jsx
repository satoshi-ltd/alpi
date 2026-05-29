import { memo, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useProfileDetail } from "../hooks/useProfileDetail.js";
import AlpiPicker from "../features/AlpiPicker.jsx";
import ToPickerBar from "../primitives/ToPickerBar.jsx";
import ModelPicker from "../features/ModelPicker.jsx";
import Button from "../primitives/Button.jsx";
import Composer from "../primitives/Composer.jsx";
import Message from "../primitives/Message.jsx";
import { useStickyScroll } from "../lib/useStickyScroll.js";
import { useScrollProgress } from "../lib/useScrollProgress.js";
import { relativeTime } from "../lib/time.js";
import { profileLabel } from "../lib/profile-display.js";
import MessageSkeleton from "../primitives/MessageSkeleton.jsx";
import SearchBar from "../primitives/SearchBar.jsx";
import { useTranscriptSearch } from "../hooks/useTranscriptSearch.js";
import { useNotify } from "../primitives/Notification.jsx";
import Logo from "../primitives/Logo.jsx";
import { renderMarkdown } from "../lib/markdown.js";
import { JumpToLatest, NewChatHero, ProfileChatHeader } from "../primitives/index.js";
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
import { playTts, subscribeTts, VOICE_POOL } from "../lib/tts.js";
import { useOnline } from "../lib/useOnline.js";
import styles from "./ChatPane.module.css";

export default function ChatPane({
  view,
  profiles,
  activeProfile,
  connectionId,
  sessionData,
  pendingTurn,
  onSend,
  onCancel,
  onSelectProfile,
  onConfigureProfile,
  onRewriteMessage,
  onRetryMessage,
  rewriteDraft,
  onRewriteDraftApplied,
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

  useEffect(() => {
    setModelOverride(null);
  }, [sessionKey]);

  // Lazy heavy fields — voice_id / models / mcps. Scoped per connection so two daemons with the same profile name never share state.
  const { detail: activeDetail } = useProfileDetail(connectionId ?? null, activeProfile?.name ?? null);
  const activeModels = activeProfile?.models ?? activeDetail?.models ?? [];

  const noModel = !!activeProfile && !activeProfile.model;
  // Pre-split: needed full provider lists from summary to decide "is the profile chat-ready?". Post-split: the daemon precomputes `has_any_provider` so we don't drag the heavy detail down the hot poll.
  const hasProviders =
    !!activeProfile &&
    (typeof activeProfile.has_any_provider === "boolean"
      ? activeProfile.has_any_provider
      : (activeProfile.models?.length ?? 0) > 0
        || (activeProfile.provider_ollama?.length ?? 0) > 0);

  if (noModel) {
    return (
      <>
        {inProfile && activeProfile && (
          <ProfileChatHeader
            profile={activeProfile}
            sessionData={sessionData}
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
          availableModels={activeModels}
          onSelectProfile={onSelectProfile}
          onConfigureProfile={onConfigureProfile}
          onSend={onSend}
          onCancel={pendingTurn ? onCancel : null}
          disabled={daemonOffline}
          daemonOffline={daemonOffline}
          showPicker={view.kind === "empty"}
          modelOverride={modelOverride}
          onModelChange={setModelOverride}
          embedded
          rewriteDraft={rewriteDraft}
          onRewriteDraftApplied={onRewriteDraftApplied}
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
      <div className={styles.body}>
        <RefreshBar
          key={refreshBeat}
          active={refreshBeat > 0}
          accent={activeProfile?.accent ?? null}
        />
        <SessionView
          data={sessionData}
          pendingTurn={pendingTurn}
          accent={activeProfile?.accent ?? null}
          showEmptyHint={inProfile && view.sessionId == null && !pendingTurn}
          profileName={activeProfile?.name ?? null}
          profileModel={activeProfile?.model ?? null}
          voiceId={activeProfile?.voice_id ?? activeDetail?.voice_id ?? null}
          onRewriteMessage={onRewriteMessage}
          onRetryMessage={onRetryMessage}
          sessionId={view.sessionId ?? null}
          rewriteDraft={rewriteDraft}
          searchOpen={searchOpen}
          onCloseSearch={onCloseSearch}
        />
      </div>
      <ChatComposer
        profiles={profiles}
        activeProfile={activeProfile}
        availableModels={activeModels}
        onSelectProfile={onSelectProfile}
        onConfigureProfile={onConfigureProfile}
        onSend={onSend}
        onCancel={pendingTurn ? onCancel : null}
        disabled={daemonOffline}
        daemonOffline={daemonOffline}
        showPicker={false}
        modelOverride={modelOverride}
        onModelChange={setModelOverride}
        rewriteDraft={rewriteDraft}
        onRewriteDraftApplied={onRewriteDraftApplied}
        minHeight={40}
      />
    </>
  );
}

function SessionView({
  data,
  pendingTurn,
  accent,
  showEmptyHint,
  profileName,
  profileModel,
  voiceId,
  onRewriteMessage,
  onRetryMessage,
  sessionId,
  rewriteDraft,
  searchOpen,
  onCloseSearch,
}) {
  return (
    <>
      <Transcript
        data={data}
        pendingTurn={pendingTurn}
        accent={accent}
        showEmptyHint={showEmptyHint}
        profileName={profileName}
        profileModel={profileModel}
        voiceId={voiceId}
        onRewriteMessage={onRewriteMessage}
        onRetryMessage={onRetryMessage}
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
  pendingTurn,
  accent,
  showEmptyHint,
  profileName,
  profileModel,
  voiceId,
  onRewriteMessage,
  onRetryMessage,
  sessionId,
  rewriteDraft,
  searchOpen,
  onCloseSearch,
}) {
  const scrollRef = useStickyScroll([data, pendingTurn]);
  const { farFromBottom, scrollToBottom } = useScrollProgress(scrollRef, {
    streaming: !!pendingTurn,
  });
  const search = useTranscriptSearch(scrollRef, searchOpen);
  const closeSearch = () => {
    search.reset();
    onCloseSearch?.();
  };
  const allTurns = data?.turns ?? [];
  const turns =
    rewriteDraft &&
    rewriteDraft.profile === profileName &&
    rewriteDraft.sessionId === sessionId &&
    Number.isInteger(rewriteDraft.turnIndex)
      ? allTurns.slice(0, rewriteDraft.turnIndex)
      : allTurns;

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
        <div className={styles.loadingUser}>
          <div className={styles.loadingUserBubble}>
            <MessageSkeleton />
          </div>
        </div>
        <div className={styles.loadingAssistant}>
          <MessageSkeleton />
        </div>
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
              turns={turns}
              accent={accent}
              profileName={profileName}
              voiceId={voiceId}
              onRewriteMessage={onRewriteMessage}
              onRetryMessage={onRetryMessage}
              sessionId={sessionId}
            />
            {pendingTurn && <PendingTurn turn={pendingTurn} accent={accent} />}
          </div>
        </div>
        <JumpToLatest show={farFromBottom} onClick={scrollToBottom} />
      </div>
    </>
  );
});

const HistoryTurns = memo(function HistoryTurns({
  turns,
  accent,
  profileName,
  voiceId,
  onRewriteMessage,
  onRetryMessage,
  sessionId,
}) {
  return (
    <>
      {turns.map((t, i) => (
        <Turn
          key={t.at ?? i}
          turn={t}
          accent={accent}
          profileName={profileName}
          voiceId={voiceId}
          sessionId={sessionId}
          turnIndex={i}
          onRewriteMessage={onRewriteMessage}
          onRetryMessage={onRetryMessage}
        />
      ))}
    </>
  );
});

const Turn = memo(function Turn({
  turn,
  accent,
  profileName,
  voiceId,
  sessionId,
  turnIndex,
  onRewriteMessage,
  onRetryMessage,
}) {
  const notify = useNotify();
  const allTools = turn.tools ?? [];
  const tools = allTools.filter((t) => t.name !== "ask_user");
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
    try {
      await navigator.clipboard.writeText(text);
      notify({ message: "Message copied", variant: "success" });
    } catch (e) {
      notify({ message: `Copy failed: ${e}`, variant: "error" });
    }
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
          {turn.user}
        </ProfileMessage>
      )}
      {tools.length > 0 && (
        <div className={styles.toolGroup}>
          {groupConsecutiveTools(tools).map((g, i) => (
            <ToolGroupCard key={`g-${i}-${g.tools[0].tool_id ?? g.name}`} group={g} accent={accent} />
          ))}
        </div>
      )}
      {askUserAnswers.map((a) => (
        <AskUserAnswer
          key={a.tool_id ?? a.result}
          result={a.result}
          question={a.question}
          accent={accent}
        />
      ))}
      {turn.assistant && !hideAssistant && (
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
          <span className="alpi-md" dangerouslySetInnerHTML={{ __html: renderMarkdown(turn.assistant) }} />
        </ProfileMessage>
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

function PendingTurn({ turn, accent }) {
  const allTools = turn.tools ?? [];
  const tools = allTools.filter((t) => t.name !== "ask_user");
  const askUserAnswers = allTools
    .filter((t) => t.name === "ask_user")
    .map((t) => ({
      tool_id: t.tool_id,
      result: (t.output || t.result || "").trim(),
      question: t.args?.question || "",
    }))
    .filter((a) => a.result);
  return (
    <div className={styles.turn}>
      {turn.user && (
        <ProfileMessage role="user" accent={accent || "var(--accent)"}>
          {turn.user}
        </ProfileMessage>
      )}
      {tools.length > 0 && (
        <div className={styles.toolGroup}>
          {groupConsecutiveTools(tools).map((g, i) => (
            <ToolGroupCard key={`g-${i}-${g.tools[0].tool_id ?? g.name}`} group={g} accent={accent} />
          ))}
        </div>
      )}
      {askUserAnswers.map((a) => (
        <AskUserAnswer
          key={a.tool_id ?? a.result}
          result={a.result}
          question={a.question}
          accent={accent}
        />
      ))}
      {turn.assistantPreview && (
        <ProfileMessage role="assistant">
          <span
            className="alpi-md"
            dangerouslySetInnerHTML={{
              __html: renderMarkdown(turn.assistantPreview),
            }}
          />
        </ProfileMessage>
      )}
      {turn.error && (
        <div className={styles.toolError}>{turn.error}</div>
      )}
      {!turn.error && !turn.assistantPreview && allTools.length === 0 && (
        <MessageSkeleton className={styles.thinking} />
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

function ChatComposer({
  profiles,
  activeProfile,
  availableModels = [],
  onSelectProfile,
  onConfigureProfile,
  onSend,
  onCancel,
  showPicker,
  embedded,
  disabled,
  daemonOffline = false,
  modelOverride,
  onModelChange,
  rewriteDraft,
  onRewriteDraftApplied,
  minHeight = null,
}) {
  const [text, setText] = useState("");
  const [baseMentions, setBaseMentions] = useState([]);
  useEffect(() => {
    if (!rewriteDraft?.text || rewriteDraft.consumed) return;
    setText(rewriteDraft.text);
    onRewriteDraftApplied?.();
  }, [rewriteDraft, onRewriteDraftApplied]);
  useEffect(() => {
    if (!activeProfile?.name) {
      setBaseMentions([]);
      return;
    }
    let cancelled = false;
    invoke("read_file", {
      profile: activeProfile.name,
      relPath: "alp/peers.yaml",
    })
      .then(async (text) => {
        if (cancelled) return;
        const parsed = parsePeerMentions(text);
        if (parsed.length === 0) {
          setBaseMentions([]);
          return;
        }
        let probes = [];
        try {
          probes = await invoke("probe_peers", {
            profile: activeProfile.name,
            ids: parsed.map((m) => m.id),
          });
        } catch {
          probes = [];
        }
        if (cancelled) return;
        const statusById = {};
        for (const r of probes ?? []) statusById[r.id] = r.status;
        setBaseMentions(parsed.map((m) => ({
          ...m,
          status: statusById[m.id] ?? "?",
        })));
      })
      .catch(() => !cancelled && setBaseMentions([]));
    return () => {
      cancelled = true;
    };
  }, [activeProfile?.name]);

  const mentions = useMemo(
    () =>
      baseMentions.map((m) => {
        const profile = profiles.find((p) => p.name === m.id);
        return { ...m, accent: profile?.accent ?? null };
      }),
    [baseMentions, profiles],
  );

  const hasText = text.trim().length > 0;
  const canSend = hasText && !!activeProfile && !daemonOffline;

  function trySend() {
    if (!canSend) return;
    const payload = text.trim();
    setText("");
    onSend?.(payload, modelOverride ?? null);
  }

  const placeholder = daemonOffline
    ? "daemon offline — sending paused"
    : disabled
      ? "thinking… (type your next message)"
      : activeProfile?.name
        ? `Message ${activeProfile.name}…`
        : "Send a message…";
  const sendTitle = daemonOffline
    ? "Daemon offline"
    : disabled
      ? "Waiting for reply"
      : "Send (⌘↵)";

  return (
    <Composer
      value={text}
      onChange={setText}
      onSubmit={trySend}
      onCancel={onCancel}
      canSend={canSend}
      embedded={embedded}
      minHeight={minHeight}
      accent={activeProfile?.accent ?? null}
      placeholder={placeholder}
      sendTitle={sendTitle}
      disabledTitle="Type a message"
      mentions={mentions}
      hint={
        <>
          <span>
            <Mono className={styles.hintAt}>@</Mono> mention
          </span>
          <span className={styles.hintKeys}>
            <Kbd>⌘</Kbd>
            <Kbd>↵</Kbd>
            <span>send</span>
          </span>
        </>
      }
      topBar={
        showPicker ? (
          <AlpiPicker
            profiles={profiles}
            activeAlpi={activeProfile?.name ?? null}
            onChange={onSelectProfile}
            variant="bar"
            modelLabel={activeProfile?.model}
          />
        ) : null
      }
      leftActions={
        <>
          {!showPicker && activeProfile && (
            <ModelPicker
              profile={activeProfile.name}
              models={availableModels}
              defaultModel={activeProfile.model ?? null}
              value={modelOverride}
              onChange={onModelChange}
              onSetDefault={onConfigureProfile ? () => onConfigureProfile(activeProfile) : null}
              accent={activeProfile.accent ?? null}
            />
          )}
        </>
      }
    />
  );
}

function parsePeerMentions(text) {
  if (!text) return [];
  const out = [];
  let cur = null;
  for (const raw of text.split("\n")) {
    if (raw.startsWith("- id:")) {
      if (cur && cur.id) out.push(cur);
      cur = { id: raw.slice("- id:".length).trim().replace(/^['"]|['"]$/g, "") };
    } else if (cur && raw.startsWith("  ")) {
      const trimmed = raw.trim();
      const i = trimmed.indexOf(":");
      if (i > 0) {
        const k = trimmed.slice(0, i).trim();
        const v = trimmed
          .slice(i + 1)
          .trim()
          .replace(/^['"]|['"]$/g, "");
        if (k === "alias") cur.hint = v;
        if (k === "address" && !cur.hint) cur.hint = v;
      }
    }
  }
  if (cur && cur.id) out.push(cur);
  return out;
}
