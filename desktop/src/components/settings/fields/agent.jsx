import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Dropdown from "../../../primitives/Dropdown.jsx";
import Modal from "../../../primitives/Modal.jsx";
import Textarea from "../../../primitives/Textarea.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Row, ConfirmButton } from "../primitives.jsx";
import { PAID_PROVIDERS, VOICE_SHORTLIST } from "../util.js";
import styles from "../../Settings.module.css";

export function ModelField({ profile, value, onChange }) {
  const [models, setModels] = useState([]);
  useEffect(() => {
    invoke("ollama_models", { profile: profile.name })
      .then((list) =>
        setModels([
          ...(profile.models ?? []),
          ...(Array.isArray(list) ? list : []),
        ]),
      )
      .catch(() => setModels(profile.models ?? []));
  }, [profile.name, profile.models]);

  const seen = new Set();
  const unique = models.filter((m) => (seen.has(m) ? false : seen.add(m)));
  const items = unique.includes(value) || !value ? unique : [value, ...unique];

  const groups = useMemo(() => {
    const m = new Map();
    for (const id of items) {
      const slash = id.indexOf("/");
      const provider = slash > 0 ? id.slice(0, slash) : "ollama";
      const label = slash > 0 ? id.slice(slash + 1) : id;
      if (!m.has(provider)) m.set(provider, []);
      m.get(provider).push({ id, label });
    }
    return m;
  }, [items]);

  return (
    <Dropdown
      trigger={{ label: value || "Select model…" }}
      direction="down"
      align="left"
      width={320}
      variant="outlined"
    >
      {({ close }) =>
        items.length === 0 ? (
          <Dropdown.Empty>No models available</Dropdown.Empty>
        ) : groups.size === 1 ? (
          items.map((m) => (
            <Dropdown.Row
              key={m}
              active={m === value}
              onClick={() => {
                onChange(m);
                close();
              }}
            >
              {m}
            </Dropdown.Row>
          ))
        ) : (
          [...groups.entries()].map(([provider, list]) => (
            <Dropdown.Group key={provider} label={provider}>
              {list.map(({ id, label }) => (
                <Dropdown.Row
                  key={id}
                  active={id === value}
                  onClick={() => {
                    onChange(id);
                    close();
                  }}
                >
                  {label}
                </Dropdown.Row>
              ))}
            </Dropdown.Group>
          ))
        )
      }
    </Dropdown>
  );
}

export function AddProviderField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const anchorRef = useRef(null);
  const popoverRef = useRef(null);
  const pos = useAutoPosition({
    open,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "right",
  });

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <span ref={wrapRef} className={styles.popoverAnchor}>
      <span ref={anchorRef}>
        <Button size="sm" onClick={() => setOpen((o) => !o)}>
          Providers
        </Button>
      </span>
      {open && (
        <div
          ref={popoverRef}
          className={styles.popover}
          style={{
            minWidth: 360,
            maxWidth: pos.maxWidth ?? undefined,
            width: 440,
            position: "fixed",
            top: pos.top,
            left: pos.left,
            right: "auto",
            bottom: "auto",
            visibility: pos.ready ? "visible" : "hidden",
          }}
        >
          <ProviderEditor
            profile={profile}
            onClose={() => setOpen(false)}
            onSaved={onSaved}
          />
        </div>
      )}
    </span>
  );
}

function ProviderEditor({ profile, onClose, onSaved }) {
  const notify = useNotify();
  const configured = profile.provider_keys ?? [];
  const configuredEnvs = new Set(configured.map((k) => k.env));
  const ollamas = profile.provider_ollama ?? [];
  const [pick, setPick] = useState("ollama");
  const [keyValue, setKeyValue] = useState("");
  const [ollamaName, setOllamaName] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [orModel, setOrModel] = useState("");
  const [busy, setBusy] = useState(false);

  const isOllama = pick === "ollama";
  const isOpenRouter = pick === "openrouter";
  const provider = PAID_PROVIDERS.find((p) => p.id === pick);
  const savedOpenRouterModels = (profile.models ?? [])
    .filter((m) => m.startsWith("openrouter/"))
    .map((m) => m.slice("openrouter/".length));

  async function save() {
    if (busy) return;
    setBusy(true);
    try {
      if (isOllama) {
        const name = ollamaName.trim();
        const url = ollamaUrl.trim().replace(/\/$/, "");
        if (!name || !/^[a-z0-9_-]+$/.test(name)) {
          throw new Error("name must be lowercase letters, digits, - or _");
        }
        if (!url) throw new Error("url required");
        await invoke("provider_add_ollama", { profile: profile.name, name, url });
        notify({ message: `Ollama @${name} added`, variant: "success" });
      } else {
        const keyAlreadySet = configuredEnvs.has(provider.env);
        const trimmedKey = keyValue.trim();
        if (!keyAlreadySet && !trimmedKey) {
          throw new Error("API key required");
        }
        const trimmedModel = orModel.trim().replace(/^openrouter\//, "");
        if (isOpenRouter && !trimmedModel) {
          throw new Error("model required");
        }
        if (trimmedKey) {
          await invoke("provider_set_key", {
            profile: profile.name,
            key: provider.env,
            value: keyValue,
          });
        }
        if (isOpenRouter && trimmedModel) {
          await invoke("provider_add_openrouter_model", {
            profile: profile.name,
            model: trimmedModel,
          });
        }
        notify({
          message: isOpenRouter
            ? `OpenRouter ${trimmedModel} ready`
            : `${provider.label} key saved`,
          variant: "success",
        });
      }
      await onSaved?.();
      onClose?.();
    } catch (e) {
      notify({
        message: `add provider: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  async function removePaid(env, label) {
    try {
      await invoke("provider_unset_key", { profile: profile.name, key: env });
      notify({ message: `${label} key cleared`, variant: "success" });
      await onSaved?.();
    } catch (e) {
      notify({ message: `clear: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  async function removeOllama(name) {
    try {
      await invoke("provider_remove_ollama", { profile: profile.name, name });
      notify({ message: `Ollama @${name} removed`, variant: "success" });
      await onSaved?.();
    } catch (e) {
      notify({ message: `remove: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  const hasAnyConfigured = configured.length > 0 || ollamas.length > 0;

  return (
    <>
      {hasAnyConfigured && (
        <div className={styles.field}>
          <label className={styles.label}>configured</label>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {PAID_PROVIDERS.filter((p) => configuredEnvs.has(p.env)).map((p) => {
              const preview =
                configured.find((k) => k.env === p.env)?.preview ?? "";
              return (
                <span
                  key={p.env}
                  className={`${styles.inlineRow} ${styles.inlineRowSpaceBetween}`}
                >
                  <span>
                    <strong>{p.label}</strong>{" "}
                    <span className={`${styles.muted} ${styles.mono}`}>
                      · {preview}
                    </span>
                  </span>
                  <ConfirmButton
                    size="sm"
                    label="Remove"
                    confirmLabel="Confirm"
                    onConfirm={() => removePaid(p.env, p.label)}
                  />
                </span>
              );
            })}
            {ollamas.map((o) => (
              <span
                key={o.name}
                className={`${styles.inlineRow} ${styles.inlineRowSpaceBetween}`}
              >
                <span>
                  <strong>Ollama @{o.name}</strong>{" "}
                  <span className={styles.muted}>· {o.url}</span>
                </span>
                <ConfirmButton
                  size="sm"
                  label="Remove"
                  confirmLabel="Confirm"
                  onConfirm={() => removeOllama(o.name)}
                />
              </span>
            ))}
          </div>
        </div>
      )}

      <div className={styles.field}>
        <label className={styles.label}>add new</label>
        <span className={styles.inlineRow}>
          <Chip
            size="sm"
            state={pick === "ollama" ? "on" : "off"}
            onClick={() => setPick("ollama")}
            tooltip="local-first · run models on your own hardware"
          >
            Ollama
          </Chip>
          {PAID_PROVIDERS.map((p) => (
            <Chip
              key={p.id}
              size="sm"
              state={pick === p.id ? "on" : "off"}
              onClick={() => setPick(p.id)}
            >
              {p.label}
            </Chip>
          ))}
        </span>
      </div>

      {isOllama ? (
        <>
          <div className={styles.field}>
            <label className={styles.label}>name</label>
            <input
              className={styles.input}
              value={ollamaName}
              onChange={(e) => setOllamaName(e.target.value.toLowerCase())}
              placeholder="local · home-gpu · cloud-a"
              spellCheck={false}
              autoFocus
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>url</label>
            <input
              className={styles.input}
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://localhost:11434"
              spellCheck={false}
            />
          </div>
        </>
      ) : (
        <>
          <div className={styles.field}>
            <label className={styles.label}>{provider.env}</label>
            <input
              className={styles.input}
              type="password"
              value={keyValue}
              onChange={(e) => setKeyValue(e.target.value)}
              placeholder={
                configuredEnvs.has(provider.env)
                  ? "(replace existing key)"
                  : "paste API key"
              }
              spellCheck={false}
              autoFocus
            />
          </div>
          {isOpenRouter && (
            <div className={styles.field}>
              <label className={styles.label}>model</label>
              <input
                className={styles.input}
                value={orModel}
                onChange={(e) => setOrModel(e.target.value)}
                placeholder="anthropic/claude-3.5-sonnet"
                spellCheck={false}
              />
              {savedOpenRouterModels.length > 0 && (
                <span
                  className={styles.inlineRow}
                  style={{ marginTop: "var(--space-3)" }}
                >
                  {savedOpenRouterModels.map((m) => (
                    <Chip
                      key={m}
                      size="sm"
                      state={orModel === m ? "on" : "off"}
                      onClick={() => setOrModel(m)}
                    >
                      {m}
                    </Chip>
                  ))}
                </span>
              )}
            </div>
          )}
        </>
      )}

      <div className={styles.actions}>
        <Button size="sm" onClick={onClose}>Close</Button>
        <Button size="sm" variant="primary" onClick={save} loading={busy}>
          Save
        </Button>
      </div>
    </>
  );
}

export function VoiceField({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const voiceId = profile.voice_id ?? "en-US-AriaNeural";
  const autoplay = !!profile.voice_autoplay;
  const current =
    VOICE_SHORTLIST.find((v) => v.id === voiceId) ?? {
      id: voiceId,
      name: voiceId,
      desc: "(custom)",
    };

  async function pickVoice(id) {
    setBusy("voice");
    try {
      await invoke("voice_set_voice", { profile: profile.name, voiceId: id });
      await onSaved?.();
    } catch (e) {
      notify({ message: `voice: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  async function toggleAutoplay() {
    setBusy("autoplay");
    try {
      await invoke("voice_autoplay", {
        profile: profile.name,
        state: autoplay ? "off" : "on",
      });
      await onSaved?.();
    } catch (e) {
      notify({ message: `autoplay: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  async function testVoice() {
    setBusy("test");
    try {
      await invoke("voice_test", { profile: profile.name, voiceId: voiceId });
    } catch (e) {
      notify({ message: `voice test: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <Row label="voice">
        <span className={styles.inlineRow}>
          <Dropdown
            trigger={{ label: `${current.name} · ${current.desc}` }}
            direction="down"
            align="left"
            width={320}
            variant="outlined"
          >
            {({ close }) =>
              VOICE_SHORTLIST.map((v) => (
                <Dropdown.Row
                  key={v.id}
                  active={v.id === voiceId}
                  caption={v.desc}
                  onClick={() => {
                    close();
                    if (v.id !== voiceId) pickVoice(v.id);
                  }}
                >
                  {v.name}
                </Dropdown.Row>
              ))
            }
          </Dropdown>
          <Button
            size="sm"
            onClick={testVoice}
            disabled={!!busy}
            loading={busy === "test"}
            title="play a localized greeting in this voice"
          >
            Test
          </Button>
        </span>
      </Row>
      <Row label="autoplay">
        <span className={styles.inlineRow}>
          <Chip
            state={autoplay ? "on" : "off"}
            tooltip={
              autoplay
                ? "speak the assistant's reply through your speakers"
                : "TTS available on demand only — no autoplay"
            }
          >
            {autoplay ? "on" : "off"}
          </Chip>
          <Button
            size="sm"
            onClick={toggleAutoplay}
            disabled={!!busy}
            loading={busy === "autoplay"}
          >
            {autoplay ? "Disable" : "Enable"}
          </Button>
        </span>
      </Row>
    </>
  );
}

export function McpField({ profile, onSaved }) {
  const [adding, setAdding] = useState(false);
  const [viewing, setViewing] = useState(null);
  const mcps = profile.mcps ?? [];

  return (
    <Row label="mcps">
      <span className={styles.gatewayChips}>
        {mcps.length === 0 && <span className={styles.muted}>none</span>}
        {mcps.map((m) => (
          <Chip
            key={m.name}
            state="on"
            onClick={() => setViewing(m.name)}
          >
            {m.name}
          </Chip>
        ))}
        <Button size="sm" onClick={() => setAdding(true)}>+ Add MCP</Button>
      </span>
      {adding && (
        <McpAddModal
          profile={profile}
          existingNames={mcps.map((m) => m.name)}
          onClose={() => setAdding(false)}
          onSaved={async () => { await onSaved?.(); setAdding(false); }}
        />
      )}
      {viewing && (
        <McpDetailModal
          profile={profile}
          mcp={mcps.find((m) => m.name === viewing)}
          onClose={() => setViewing(null)}
          onRemoved={async () => { await onSaved?.(); setViewing(null); }}
        />
      )}
    </Row>
  );
}

function McpDetailModal({ profile, mcp, onClose, onRemoved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(false);

  if (!mcp) return null;

  async function remove() {
    setBusy(true);
    try {
      await invoke("mcp_remove", { profile: profile.name, name: mcp.name });
      notify({ message: `MCP @${mcp.name} removed`, variant: "success" });
      onRemoved();
    } catch (e) {
      notify({ message: `remove: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`MCP · ${mcp.name}`} onClose={onClose}>
      <div className={styles.field}>
        <label className={styles.label}>command</label>
        <span className={styles.mono}>{mcp.command || "(none)"}</span>
      </div>
      <div className={styles.field}>
        <label className={styles.label}>args</label>
        <span className={styles.mono}>
          {(mcp.args ?? []).length === 0
            ? "(none)"
            : (mcp.args ?? []).join(" ")}
        </span>
      </div>
      <div className={styles.field}>
        <label className={styles.label}>env</label>
        <span className={styles.inlineRow}>
          {(mcp.env_keys ?? []).length === 0 ? (
            <span className={styles.muted}>none</span>
          ) : (
            (mcp.env_keys ?? []).map((k) => (
              <Chip key={k} size="sm" state="on">{k}</Chip>
            ))
          )}
        </span>
      </div>
      <div className={styles.muted} style={{ fontSize: "var(--font-size-tiny)" }}>
        To edit, remove and add again. Env values are never read back from disk.
      </div>
      <div className={styles.actions}>
        <ConfirmButton
          size="sm"
          label="Remove"
          confirmLabel="Confirm remove"
          loading={busy}
          onConfirm={remove}
        />
        <Button size="sm" onClick={onClose} disabled={busy}>Close</Button>
      </div>
    </Modal>
  );
}

function McpAddModal({ profile, existingNames, onClose, onSaved }) {
  const notify = useNotify();
  const [name, setName] = useState("");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [envText, setEnvText] = useState("");
  const [busy, setBusy] = useState(false);

  const trimmed = name.trim();
  const validName = trimmed !== "" && /^[a-z0-9_-]+$/.test(trimmed);
  const duplicate = existingNames.includes(trimmed);
  const validCommand = command.trim() !== "";
  const canSubmit = validName && validCommand && !duplicate && !busy;

  async function save() {
    if (!canSubmit) return;
    setBusy(true);
    try {
      const envPairs = envText
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l && l.includes("="));
      await invoke("mcp_add", {
        profile: profile.name,
        name: trimmed,
        command: command.trim(),
        args: args.trim(),
        env: envPairs,
      });
      notify({ message: `MCP @${trimmed} added`, variant: "success" });
      onSaved();
    } catch (e) {
      notify({ message: `add MCP: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Add MCP server" onClose={onClose}>
      <div className={styles.muted} style={{ marginBottom: "var(--space-2)" }}>
        Example — GitHub MCP: command <code>npx</code>, args{" "}
        <code>-y @modelcontextprotocol/server-github</code>, env{" "}
        <code>GITHUB_TOKEN=ghp_…</code>.
      </div>
      <div className={styles.field}>
        <label className={styles.label}>name</label>
        <input
          className={`${styles.input} ${styles.inputFull}`}
          value={name}
          onChange={(e) => setName(e.target.value.toLowerCase())}
          placeholder="github · notion · linear"
          spellCheck={false}
          autoFocus
        />
        {duplicate && (
          <span className={styles.error} style={{ marginTop: "var(--space-2)" }}>
            @{trimmed} already exists
          </span>
        )}
      </div>
      <div className={styles.field}>
        <label className={styles.label}>command</label>
        <input
          className={`${styles.input} ${styles.inputFull}`}
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder="npx · uvx · python · /path/to/server"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label}>args</label>
        <input
          className={`${styles.input} ${styles.inputFull}`}
          value={args}
          onChange={(e) => setArgs(e.target.value)}
          placeholder="space-separated · use quotes for grouping"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label}>env (KEY=VALUE per line)</label>
        <Textarea
          className={`${styles.textarea} ${styles.inputFull}`}
          rows={3}
          value={envText}
          onChange={(e) => setEnvText(e.target.value)}
          placeholder={"GITHUB_TOKEN=ghp_xxx\nFOO=bar"}
          spellCheck={false}
        />
      </div>
      <div className={styles.actions}>
        <Button size="sm" onClick={onClose} disabled={busy}>Close</Button>
        <Button
          size="sm"
          variant="primary"
          onClick={save}
          disabled={!canSubmit}
          loading={busy}
        >
          Add
        </Button>
      </div>
    </Modal>
  );
}
