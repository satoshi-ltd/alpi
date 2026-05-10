import { memo, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import AlpiPicker from "./AlpiPicker.jsx";
import ModelPicker from "./ModelPicker.jsx";
import Button from "../primitives/Button.jsx";
import Composer from "../primitives/Composer.jsx";
import { AlpiIcon, CopyIcon, SpinnerIcon, UndoIcon } from "../primitives/icons.jsx";
import Message from "../primitives/Message.jsx";
import { useStickyScroll } from "../lib/useStickyScroll.js";
import { relativeTime } from "../lib/time.js";
import { profileLabel } from "../lib/profile-display.js";
import Skeleton from "../primitives/Skeleton.jsx";
import { useNotify } from "../primitives/Notification.jsx";
import alpiHeadUrl from "../assets/alpi-head.svg?url";
import styles from "./ChatPane.module.css";

export default function ChatPane({
  view,
  profiles,
  activeProfile,
  sessionData,
  pendingTurn,
  onSend,
  onCancel,
  onSelectProfile,
  onConfigureProfile,
  onRewriteMessage,
  rewriteDraft,
  onRewriteDraftApplied,
  daemonOffline = false,
}) {
  const inProfile = view.kind === "profile";
  // "empty view" covers both `+ New Chat` and `select a profile with no
  // existing session yet` — same UX (centered picker + composer).
  const inEmpty =
    !pendingTurn &&
    (view.kind === "empty" ||
      (view.kind === "profile" && view.sessionId == null));
  const sessionKey = inProfile ? `${view.profile}:${view.sessionId ?? "new"}` : "empty";
  const [modelOverride, setModelOverride] = useState(null);

  useEffect(() => {
    setModelOverride(null);
  }, [sessionKey]);

  const noModel = !!activeProfile && !activeProfile.model;
  const hasProviders =
    !!activeProfile &&
    ((activeProfile.models?.length ?? 0) > 0 ||
      (activeProfile.provider_ollama?.length ?? 0) > 0);

  // Hide the chat until the active profile has a model.
  if (noModel) {
    return (
      <div className={styles.emptyShell}>
        <div className={styles.emptyContent}>
          <div className={styles.emptyMark}>
            <Logo />
          </div>
          <div className={styles.titleGroup}>
            <h1 className={styles.emptyHeading}>
              {hasProviders
                ? `@${profileLabel(activeProfile.name)} needs a model`
                : `@${profileLabel(activeProfile.name)} needs a provider`}
            </h1>
            <p className={styles.emptyHint}>
              {hasProviders
                ? "Pick from one of the providers you've already connected."
                : "Connect Anthropic, OpenAI, OpenRouter, Gemini or Ollama to start chatting."}
            </p>
          </div>
          <Button
            variant="primary"
            onClick={() => onConfigureProfile?.(activeProfile)}
          >
            {hasProviders ? "Pick a model" : "Set up provider"}
          </Button>
        </div>
      </div>
    );
  }

  if (inEmpty) {
    return (
      <div className={styles.emptyShell}>
        <div className={styles.emptyContent}>
          <div className={styles.emptyMark}>
            <Logo />
          </div>
          <h1 className={styles.emptyHeading}>What's on your mind?</h1>
          {activeProfile && (
            <div className={styles.emptyHint}>
              chatting with <strong>{activeProfile.name}</strong>
              {activeProfile.model && (
                <>
                  {" · "}
                  <span className={styles.emptyModel}>
                    {activeProfile.model}
                  </span>
                </>
              )}
            </div>
          )}
          <ChatComposer
            profiles={profiles}
            activeProfile={activeProfile}
            onSelectProfile={onSelectProfile}
            onSend={onSend}
            onCancel={pendingTurn ? onCancel : null}
            disabled={daemonOffline}
            daemonOffline={daemonOffline}
            showPicker
            embedded
            rewriteDraft={rewriteDraft}
            onRewriteDraftApplied={onRewriteDraftApplied}
          />
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={styles.body}>
        <SessionView
          data={sessionData}
          pendingTurn={pendingTurn}
          accent={activeProfile?.accent ?? null}
          showEmptyHint={inProfile && view.sessionId == null && !pendingTurn}
          profileName={activeProfile?.name ?? null}
          onRewriteMessage={onRewriteMessage}
          sessionId={view.sessionId ?? null}
          rewriteDraft={rewriteDraft}
        />
      </div>
      <ChatComposer
        profiles={profiles}
        activeProfile={activeProfile}
        onSelectProfile={onSelectProfile}
        onSend={onSend}
        onCancel={pendingTurn ? onCancel : null}
        disabled={daemonOffline}
        daemonOffline={daemonOffline}
        showPicker={false}
        modelOverride={modelOverride}
        onModelChange={setModelOverride}
        rewriteDraft={rewriteDraft}
        onRewriteDraftApplied={onRewriteDraftApplied}
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
  onRewriteMessage,
  sessionId,
  rewriteDraft,
}) {
  return (
    <>
      <Transcript
        data={data}
        pendingTurn={pendingTurn}
        accent={accent}
        showEmptyHint={showEmptyHint}
        profileName={profileName}
        onRewriteMessage={onRewriteMessage}
        sessionId={sessionId}
        rewriteDraft={rewriteDraft}
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
  onRewriteMessage,
  sessionId,
  rewriteDraft,
}) {
  const scrollRef = useStickyScroll([data, pendingTurn]);
  const allTurns = data?.turns ?? [];
  const turns =
    rewriteDraft &&
    rewriteDraft.profile === profileName &&
    rewriteDraft.sessionId === sessionId &&
    Number.isInteger(rewriteDraft.turnIndex)
      ? allTurns.slice(0, rewriteDraft.turnIndex)
      : allTurns;

  if (showEmptyHint) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyMark}>
          <Logo />
        </div>
        <div className={styles.emptyHint}>
          new chat with <strong>{profileName}</strong>
        </div>
      </div>
    );
  }

  if (turns.length === 0 && !data) {
    return (
      <div className={styles.loading}>
        <Skeleton width="60%" height="1.2em" />
        <Skeleton width="80%" height="1.2em" />
        <Skeleton width="45%" height="1.2em" />
      </div>
    );
  }

  return (
    <div ref={scrollRef} className={styles.transcript}>
      <div className={styles.timeline}>
        <HistoryTurns
          turns={turns}
          accent={accent}
          profileName={profileName}
          onRewriteMessage={onRewriteMessage}
          sessionId={sessionId}
        />
        {pendingTurn && <PendingTurn turn={pendingTurn} accent={accent} />}
      </div>
    </div>
  );
});

const HistoryTurns = memo(function HistoryTurns({
  turns,
  accent,
  profileName,
  onRewriteMessage,
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
          sessionId={sessionId}
          turnIndex={i}
          onRewriteMessage={onRewriteMessage}
        />
      ))}
    </>
  );
});

const Turn = memo(function Turn({
  turn,
  accent,
  profileName,
  sessionId,
  turnIndex,
  onRewriteMessage,
}) {
  const notify = useNotify();
  const tools = turn.tools ?? [];
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
        <Message
          align="right"
          bubble
          accent={accent ?? "#c8a24e"}
          body={turn.user}
          markdown={false}
          footer={
            <>
              <span className={styles.messageTime}>{relativeTime(turn.at)}</span>
              {onRewriteMessage && (
                <Button
                  icon={<UndoIcon />}
                  size="xs"
                  title="Rewrite from here"
                  onClick={() => onRewriteMessage(
                    profileName,
                    sessionId,
                    turnIndex,
                    turn.user,
                  )}
                />
              )}
              <Button
                icon={<CopyIcon />}
                size="xs"
                title="Copy message"
                onClick={() => copyMessage(turn.user)}
              />
            </>
          }
        />
      )}
      {tools.length > 0 && (
        <div className={styles.toolGroup}>
          {tools.map((t, i) => (
            <ToolCard
              key={t.tool_id ?? `${t.name}:${i}`}
              name={t.name}
              preview={previewForArgs(t.args)}
              ok={t.ok ?? true}
              accent={accent}
            />
          ))}
        </div>
      )}
      {turn.assistant && (
        <Message
          align="left"
          body={turn.assistant}
          markdown
          footer={
            <>
              <Button
                icon={<CopyIcon />}
                size="xs"
                title="Copy message"
                onClick={() => copyMessage(turn.assistant)}
              />
              <span className={styles.messageTime}>{relativeTime(turn.at)}</span>
            </>
          }
        />
      )}
    </div>
  );
});

function previewForArgs(args) {
  if (!args || typeof args !== "object") return "";
  const entries = Object.entries(args).slice(0, 2);
  return entries
    .map(([k, v]) => {
      if (typeof v === "string") {
        const compact = v.length > 60 ? v.slice(0, 60) + "…" : v;
        return `${k}=${compact}`;
      }
      return `${k}=${JSON.stringify(v)}`;
    })
    .join(" ");
}

function PendingTurn({ turn, accent }) {
  const tools = turn.tools ?? [];
  return (
    <div className={styles.turn}>
      {turn.user && (
        <Message
          align="right"
          bubble
          accent={accent ?? "#c8a24e"}
          body={turn.user}
          markdown={false}
        />
      )}
      {tools.length > 0 && (
        <div className={styles.toolGroup}>
          {tools.map((t, i) => (
            <ToolCard
              key={t.tool_id || i}
              name={t.name}
              preview={t.preview}
              ok={t.ok}
              accent={accent}
              states={t.states}
              output={t.output}
            />
          ))}
        </div>
      )}
      {turn.assistantPreview && (
        <Message
          align="left"
          body={turn.assistantPreview}
          markdown
        />
      )}
      {turn.error && (
        <div className={styles.toolError}>{turn.error}</div>
      )}
      {!turn.error && !turn.assistantPreview && (
        <div className={styles.thinking}>
          <span className={styles.thinkingDot} />
          <span className={styles.thinkingDot} />
          <span className={styles.thinkingDot} />
        </div>
      )}
    </div>
  );
}

const ToolCard = memo(function ToolCard({ name, preview, ok, accent, states = [], output = "" }) {
  const status = ok === null ? "running" : ok ? "ok" : "fail";
  const iconStyle = status === "ok" && accent ? { color: accent } : undefined;
  const [expanded, setExpanded] = useState(false);
  const hasOutput = Boolean(output && output.trim());
  const headerClickable = hasOutput || states.length > 0;
  return (
    <div className={`${styles.tool} ${styles[`tool_${status}`]}`}>
      <button
        type="button"
        className={styles.toolHeader}
        onClick={headerClickable ? () => setExpanded((v) => !v) : undefined}
        disabled={!headerClickable}
      >
        <span className={styles.toolIcon} style={iconStyle}>
          {status === "running" ? <SpinnerIcon className={styles.spinner} /> : <AlpiIcon size={8} color="currentColor" />}
        </span>
        <span className={styles.toolName}>{name}</span>
        {preview && <span className={styles.toolPreview}>{preview}</span>}
        {headerClickable && (
          <span className={styles.toolChevron}>{expanded ? "▾" : "▸"}</span>
        )}
      </button>
      {(expanded || status === "running") && states.length > 0 && (
        <div className={styles.toolStates}>
          {states.map((s, i) => (
            <div
              key={i}
              className={`${styles.toolStateLine} ${
                s.ok === false ? styles.toolStateLineErr : ""
              }`}
            >
              {s.text}
            </div>
          ))}
        </div>
      )}
      {expanded && hasOutput && (
        <pre className={styles.toolOutput}>{output}</pre>
      )}
    </div>
  );
});


function ChatComposer({
  profiles,
  activeProfile,
  onSelectProfile,
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
  // Send can interrupt the in-flight turn from App.jsx.
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
      : "Send a message…";
  const sendTitle = daemonOffline
    ? "Daemon offline"
    : disabled
      ? "Waiting for reply"
      : "Send (Enter)";

  return (
    <Composer
      value={text}
      onChange={setText}
      onSubmit={trySend}
      onCancel={onCancel}
      canSend={canSend}
      embedded={embedded}
      placeholder={placeholder}
      sendTitle={sendTitle}
      disabledTitle="Type a message"
      mentions={mentions}
      leftActions={
        <>
          {showPicker && (
            <AlpiPicker
              profiles={profiles}
              activeAlpi={activeProfile?.name ?? null}
              onChange={onSelectProfile}
            />
          )}
          {!showPicker && activeProfile && (
            <ModelPicker
              profile={activeProfile.name}
              models={activeProfile.models ?? []}
              defaultModel={activeProfile.model ?? null}
              value={modelOverride}
              onChange={onModelChange}
            />
          )}
        </>
      }
    />
  );
}

// Parse the `peers.yaml` list used by the composer.
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

function Logo() {
  return (
    <span
      className={styles.logoImage}
      style={{ "--mask-image": `url(${alpiHeadUrl})` }}
      aria-label="alpi"
    />
  );
}
