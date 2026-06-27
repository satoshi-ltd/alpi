import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Modal from "../../../primitives/Modal.jsx";
import Textarea from "../../../primitives/Textarea.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Row } from "../primitives.jsx";
import { Btn } from "../../../primitives/index.js";
import Field from "../../../primitives/Field.jsx";
import { ConfirmDeleteAction, DialogFooter } from "../../../primitives/index.js";
import styles from "../Settings.module.css";

export function McpField({ profile, onSaved }) {
  const [adding, setAdding] = useState(false);
  const [viewing, setViewing] = useState(null);
  const mcps = profile.mcps ?? [];

  return (
    <Row label="mcps">
      <span className={styles.chipRow}>
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
        <Eyebrow as="label">command</Eyebrow>
        <span className={styles.mono}>{mcp.command || "(none)"}</span>
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">args</Eyebrow>
        <span className={styles.mono}>
          {(mcp.args ?? []).length === 0
            ? "(none)"
            : (mcp.args ?? []).join(" ")}
        </span>
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">env</Eyebrow>
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
      <div className={styles.muted} style={{ fontSize: "var(--fs-xs)" }}>
        To edit, remove and add again. Env values are never read back from disk.
      </div>
      <div className={styles.popoverFooter}>
        <ConfirmDeleteAction
          label="Remove"
          title={`Remove MCP @${mcp.name}?`}
          consequence="The server is unregistered from this profile. Env values cannot be read back from disk afterwards."
          confirmLabel="Remove"
          loading={busy}
          onConfirm={remove}
        />
        <span className={styles.popoverFooterRight}>
          <Btn variant="ghost" onClick={onClose} disabled={busy}>Close</Btn>
        </span>
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
        <Eyebrow as="label">name</Eyebrow>
        <Field
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
        <Eyebrow as="label">command</Eyebrow>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder="npx · uvx · python · /path/to/server"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">args</Eyebrow>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          value={args}
          onChange={(e) => setArgs(e.target.value)}
          placeholder="space-separated · use quotes for grouping"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">env (KEY=VALUE per line)</Eyebrow>
        <Textarea
          className={`${styles.textarea} ${styles.inputFull}`}
          rows={3}
          value={envText}
          onChange={(e) => setEnvText(e.target.value)}
          placeholder={"GITHUB_TOKEN=ghp_xxx\nFOO=bar"}
          spellCheck={false}
        />
      </div>
      <DialogFooter
        onCancel={onClose}
        primaryLabel="Add"
        primaryDisabled={!canSubmit}
        primaryLoading={busy}
        onPrimary={save}
      />
    </Modal>
  );
}
