import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import AlpiPicker from "./AlpiPicker.jsx";
import ModelPicker from "./ModelPicker.jsx";
import Composer from "../primitives/Composer.jsx";
import Message from "../primitives/Message.jsx";
import { useStickyScroll } from "../lib/useStickyScroll.js";
import alpiHeadUrl from "../assets/alpi-head.svg?url";
import styles from "./ChatPane.module.css";

export default function ChatPane({
  view,
  profiles,
  activeProfile,
  sessionData,
  pendingTurn,
  onSend,
  onSelectProfile,
}) {
  const inProfile = view.kind === "profile";
  const inEmpty = view.kind === "empty" && !pendingTurn;
  const sessionKey = inProfile ? `${view.profile}:${view.sessionId ?? "new"}` : "empty";
  const [modelOverride, setModelOverride] = useState(null);

  useEffect(() => {
    setModelOverride(null);
  }, [sessionKey]);

  const noModel = !!activeProfile && !activeProfile.model;

  // Hide the chat until the active profile has a model.
  if (noModel) {
    return (
      <div className={styles.emptyShell}>
        <div className={styles.emptyContent}>
          <div className={styles.emptyMark}>
            <Logo />
          </div>
          <h1 className={styles.emptyHeading}>No model configured</h1>
          <div className={styles.emptyHint}>
            <strong>@{activeProfile.name}</strong> has no model set. Pick
            one in <strong>Settings → Overview → model</strong> or run{" "}
            <code>alpi -p {activeProfile.name} setup</code>.
          </div>
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
            disabled={!!pendingTurn}
            showPicker
            embedded
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
        />
      </div>
      <ChatComposer
        profiles={profiles}
        activeProfile={activeProfile}
        onSelectProfile={onSelectProfile}
        onSend={onSend}
        disabled={!!pendingTurn}
        showPicker={false}
        modelOverride={modelOverride}
        onModelChange={setModelOverride}
      />
    </>
  );
}

function SessionView({ data, pendingTurn, accent, showEmptyHint, profileName }) {
  const scrollRef = useStickyScroll([data, pendingTurn]);

  const turns = data?.turns ?? [];
  const hasContent = turns.length > 0 || pendingTurn;

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

  if (!hasContent && !data) {
    return <div className={styles.loading}>loading…</div>;
  }

  return (
    <div ref={scrollRef} className={styles.transcript}>
      {turns.map((t, i) => (
        <Turn key={i} turn={t} accent={accent} />
      ))}
      {pendingTurn && <PendingTurn turn={pendingTurn} accent={accent} />}
    </div>
  );
}

function Turn({ turn, accent }) {
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
      {tools.map((t, i) => (
        <ToolCard
          key={i}
          name={t.name}
          preview={previewForArgs(t.args)}
          ok={t.ok ?? true}
          accent={accent}
        />
      ))}
      {turn.assistant && (
        <Message align="left" body={turn.assistant} markdown />
      )}
    </div>
  );
}

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

function ToolCard({ name, preview, ok, accent, states = [], output = "" }) {
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
          {status === "running" ? <Spinner /> : "◆"}
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
}

function Spinner() {
  return (
    <svg className={styles.spinner} width="12" height="12" viewBox="0 0 12 12">
      <circle
        cx="6"
        cy="6"
        r="4.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="20 30"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ChatComposer({
  profiles,
  activeProfile,
  onSelectProfile,
  onSend,
  showPicker,
  embedded,
  disabled,
  modelOverride,
  onModelChange,
}) {
  const [text, setText] = useState("");
  const [mentions, setMentions] = useState([]);
  useEffect(() => {
    if (!activeProfile?.name) {
      setMentions([]);
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
          setMentions([]);
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
        const enriched = parsed.map((m) => {
          const profile = profiles.find((p) => p.name === m.id);
          return {
            ...m,
            accent: profile?.accent ?? null,
            status: statusById[m.id] ?? "?",
          };
        });
        setMentions(enriched);
      })
      .catch(() => !cancelled && setMentions([]));
    return () => {
      cancelled = true;
    };
  }, [activeProfile?.name, profiles]);

  const hasText = text.trim().length > 0;
  // Send can interrupt the in-flight turn from App.jsx.
  const canSend = hasText && !!activeProfile;

  function trySend() {
    if (!canSend) return;
    const payload = text.trim();
    setText("");
    onSend?.(payload, modelOverride ?? null);
  }

  return (
    <Composer
      value={text}
      onChange={setText}
      onSubmit={trySend}
      canSend={canSend}
      embedded={embedded}
      placeholder={
        disabled ? "thinking… (type your next message)" : "Send a message…"
      }
      sendTitle={disabled ? "Waiting for reply" : "Send (Enter)"}
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
      className={styles.logoMask}
      style={{ "--mask-image": `url(${alpiHeadUrl})` }}
      role="img"
      aria-label="alpi"
    />
  );
}
