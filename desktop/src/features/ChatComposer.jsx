import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import AttachmentChips from "../primitives/AttachmentChips.jsx";
import { PaperclipIcon } from "../primitives/icons.jsx";
import AlpiPicker from "./AlpiPicker.jsx";
import ModelPicker from "./ModelPicker.jsx";
import Composer from "../primitives/Composer.jsx";
import { IconBtn, Kbd, Mono } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { attachmentMimeFor } from "../lib/fileKind.js";
import { clearDraft, getDraft, setDraft } from "../lib/drafts.js";
// Shares ChatPane's stylesheet on purpose — the composer renders inside the pane and reuses its class vocabulary.
import styles from "../pages/ChatPane.module.css";

export default function ChatComposer({
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
  paused = false,
  modelOverride,
  onModelChange,
  rewriteDraft,
  onRewriteDraftApplied,
  pendingAttachment,
  onPendingAttachmentApplied,
  minHeight = null,
  connectionId = null,
}) {
  const notify = useNotify();
  const draftKey = activeProfile
    ? `chat|${activeProfile.pubkey_b64 || activeProfile.name}`
    : null;
  const [text, setText] = useState(() => getDraft(draftKey));
  const draftKeyRef = useRef(draftKey);
  useEffect(() => {
    if (draftKeyRef.current === draftKey) return;
    draftKeyRef.current = draftKey;
    setText(getDraft(draftKey));
  }, [draftKey]);
  const updateText = useCallback((next) => {
    setText(next);
    setDraft(draftKeyRef.current, next);
  }, []);
  const [baseMentions, setBaseMentions] = useState([]);
  const [attachments, setAttachments] = useState([]);

  const addPaths = useCallback(async (paths) => {
    if (!paths?.length) return;
    let metas = [];
    try {
      metas = await invoke("attachment_meta", { paths });
    } catch {
      return;
    }
    setAttachments((prev) => {
      const seen = new Set(prev.map((a) => a.path));
      const rejected = [];
      const add = [];
      for (const m of metas) {
        if (!m || seen.has(m.path)) continue;
        const mime = attachmentMimeFor(m.name);
        if (!mime) {
          rejected.push(m.name);
          continue;
        }
        add.push({ path: m.path, name: m.name, size: m.size, mime });
      }
      if (rejected.length) {
        notify({
          message: `Unsupported attachment type: ${rejected.join(", ")}`,
          variant: "error",
        });
      }
      return [...prev, ...add];
    });
  }, [notify]);

  // Native (Tauri) file drop anywhere on the window adds to the composer.
  useEffect(() => {
    let unlisten;
    (async () => {
      try {
        const { getCurrentWebview } = await import("@tauri-apps/api/webview");
        unlisten = await getCurrentWebview().onDragDropEvent((e) => {
          if (e.payload?.type === "drop" && Array.isArray(e.payload.paths)) {
            addPaths(e.payload.paths);
          }
        });
      } catch {
        // not in a tauri webview (e.g. tests) — no drag-drop
      }
    })();
    return () => { try { unlisten?.(); } catch {} };
  }, [addPaths]);
  useEffect(() => {
    if (!rewriteDraft?.text || rewriteDraft.consumed) return;
    updateText(rewriteDraft.text);
    onRewriteDraftApplied?.();
  }, [rewriteDraft, onRewriteDraftApplied, updateText]);
  useEffect(() => {
    const att = pendingAttachment?.attachment;
    if (!att || pendingAttachment.consumed) return;
    if (pendingAttachment.profile && pendingAttachment.profile !== activeProfile?.name) return;
    if (pendingAttachment.connectionId && connectionId && pendingAttachment.connectionId !== connectionId) return;
    setAttachments((prev) => (prev.some((a) => a.path === att.path) ? prev : [...prev, att]));
    onPendingAttachmentApplied?.();
  }, [pendingAttachment, onPendingAttachmentApplied, activeProfile?.name, connectionId]);
  useEffect(() => {
    if (!activeProfile?.name) {
      setBaseMentions([]);
      return;
    }
    let cancelled = false;
    invoke("read_file", {
      profile: activeProfile.name,
      relPath: "alp/peers.yaml",
      ...(connectionId ? { connectionId } : {}),
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
  }, [activeProfile?.name, connectionId]);

  const mentions = useMemo(
    () =>
      baseMentions.map((m) => {
        const profile = profiles.find((p) => p.name === m.id);
        return { ...m, accent: profile?.accent ?? null };
      }),
    [baseMentions, profiles],
  );

  const hasText = text.trim().length > 0;
  const canSend = (hasText || attachments.length > 0) && !!activeProfile && !daemonOffline && !paused;

  function trySend() {
    if (!canSend) return;
    const payload = text.trim();
    const atts = attachments;
    setText("");
    clearDraft(draftKeyRef.current);
    setAttachments([]);
    onSend?.(payload, modelOverride ?? null, {
      attachments: atts.map((a) => ({ path: a.path, name: a.name, mime: a.mime, size: a.size })),
    });
  }

  const placeholder = daemonOffline
    ? "daemon offline — sending paused"
    : paused
      ? "Paused — resume to chat"
      : activeProfile?.name
        ? `Message ${activeProfile.name}…`
        : "Send a message…";
  const sendTitle = daemonOffline
    ? "Daemon offline"
    : paused
      ? "Profile is paused"
      : "Send (⌘↵)";

  return (
    <Composer
      value={text}
      onChange={updateText}
      onSubmit={trySend}
      onCancel={onCancel}
      canSend={canSend}
      disabled={paused}
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
        (showPicker || attachments.length > 0) ? (
          <>
            {showPicker ? (
              <AlpiPicker
                profiles={profiles}
                activeAlpi={activeProfile?.name ?? null}
                onChange={onSelectProfile}
                variant="bar"
                modelLabel={activeProfile?.model}
              />
            ) : null}
            <AttachmentChips
              items={attachments}
              onRemove={(i) => setAttachments((p) => p.filter((_, j) => j !== i))}
            />
          </>
        ) : null
      }
      leftActions={
        <>
          <IconBtn
            aria-label="Attach files"
            title="Attach image, PDF, or text file"
            disabled={disabled || daemonOffline}
            onClick={async () => {
              try {
                const paths = await invoke("pick_files");
                await addPaths(paths);
              } catch (e) {
                notify({ message: String(e), variant: "error" });
              }
            }}
          >
            <PaperclipIcon />
          </IconBtn>
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
