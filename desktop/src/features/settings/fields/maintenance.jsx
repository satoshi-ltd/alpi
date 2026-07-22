import { useCallback, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { createSwrCache } from "../../../lib/swr-cache.js";
import { useSwrValue } from "../../../hooks/useSwrValue.js";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import { Row } from "../primitives.jsx";
import { ConfirmDelete } from "../../../primitives/index.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Btn } from "../../../primitives/index.js";
import { STORAGE_GROUPS, RECLAIM_NOTES, formatBytes } from "../util.js";
import styles from "../Settings.module.css";

function storageCacheKey(connectionId, profileName) {
  return `${connectionId || "local"}|${profileName}`;
}

const _storageCache = createSwrCache({
  fetcher: ({ profile, connectionId }) =>
    invoke("profile_storage", { profile, ...(connectionId ? { connectionId } : {}) })
      .then((rows) => (Array.isArray(rows) ? rows : [])),
});

export function _clearStorageCache() {
  _storageCache.clear();
}

export function StorageField({ profile, activeConnection, prefetched, onLoadingChange = null, onCleaned }) {
  const notify = useNotify();
  const connectionId = activeConnection?.id ?? null;
  const canClean = activeConnection?.kind === "local" || activeConnection?.role === "admin";
  const key = storageCacheKey(connectionId, profile.name);

  const { data: usage, error, loading } = useSwrValue(
    _storageCache,
    key,
    { profile: profile.name, connectionId },
    { prefetched },
  );

  const [plan, setPlan] = useState(null);
  const [usageOverride, setUsageOverride] = useState(null);
  const [busy, setBusy] = useState(false);
  const [confirmKey, setConfirmKey] = useState(null);

  const fetchPlan = useCallback(() => {
    if (!canClean) {
      setPlan([]);
      return Promise.resolve();
    }
    return invoke("cleanup_plan", { profile: profile.name, ...(connectionId ? { connectionId } : {}) })
      .then((rows) => setPlan(Array.isArray(rows) ? rows : []))
      .catch(() => setPlan([]));
  }, [profile.name, connectionId, canClean]);

  useEffect(() => {
    setPlan(null);
    setUsageOverride(null);
    setConfirmKey(null);
    fetchPlan();
  }, [fetchPlan]);

  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);
  useEffect(() => () => onLoadingChange?.(false), [onLoadingChange]);

  const usageBy = useMemo(() => {
    const m = {};
    for (const r of usageOverride ?? usage ?? []) m[r.key] = r;
    return m;
  }, [usageOverride, usage]);
  const planByGroup = useMemo(() => {
    const m = {};
    for (const r of plan ?? []) (m[r.group] ??= []).push(r);
    return m;
  }, [plan]);

  const doClean = useCallback(async (keys, label) => {
    if (busy || keys.length === 0) return;
    setBusy(true);
    try {
      const results = await invoke("cleanup_apply", {
        profile: profile.name,
        keys,
        ...(connectionId ? { connectionId } : {}),
      });
      const rows = Array.isArray(results) ? results : [];
      const failed = rows.filter((r) => !r.ok);
      const freed = rows.reduce((n, r) => n + (r.freed_bytes ?? 0), 0);
      const removed = rows.reduce((n, r) => n + (r.removed ?? 0), 0);
      if (failed.length > 0) {
        notify({ message: `${label}: ${failed[0].errors?.[0] ?? "cleanup failed"}`, variant: "error", duration: 4000 });
      } else {
        notify({ message: `${label}: freed ${formatBytes(freed)}`, variant: "success" });
      }
      await fetchPlan();
      if (removed > 0) {
        _clearStorageCache();
        const fresh = await invoke("profile_storage", {
          profile: profile.name,
          ...(connectionId ? { connectionId } : {}),
        }).catch(() => null);
        if (Array.isArray(fresh)) setUsageOverride(fresh);
        onCleaned?.();
      }
    } catch (e) {
      notify({ message: `${label}: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(false);
    }
  }, [busy, profile.name, connectionId, notify, fetchPlan, onCleaned]);

  const groups = useMemo(() => STORAGE_GROUPS.map((g) => {
    const usageRows = g.usage.map((k) => usageBy[k]).filter(Boolean);
    return {
      key: g.key,
      label: g.label,
      desc: g.desc,
      size: usageRows.reduce((n, r) => n + r.size_bytes, 0),
      count: usageRows.reduce((n, r) => n + r.file_count, 0),
      reclaimable: (planByGroup[g.key] ?? []).some((m) => m.size > 0),
    };
  }).filter((g) => g.size > 0 || g.count > 0 || g.reclaimable), [usageBy, planByGroup]);

  const safeMembers = useMemo(
    () => (plan ?? []).filter((m) => !m.destructive && m.size > 0),
    [plan],
  );
  const safeKeys = safeMembers.map((m) => m.key);
  const safeSize = safeMembers.reduce((n, m) => n + m.size, 0);
  const destructive = useMemo(
    () => (plan ?? []).filter((m) => m.destructive && m.size > 0),
    [plan],
  );

  if (usageOverride == null && usage == null && !error) {
    return <Row label="storage"><span className={styles.muted}>loading…</span></Row>;
  }
  if (groups.length === 0) {
    return <Row label="storage"><span className={styles.muted}>nothing yet</span></Row>;
  }

  return (
    <>
      {groups.map((g) => (
        <Row key={g.key} label={g.label}>
          <span className={styles.inlineRow}>
            <Chip size="sm" tooltip={g.desc}>{formatBytes(g.size)}</Chip>
            <Chip size="sm">{g.count} {g.count === 1 ? "file" : "files"}</Chip>
          </span>
        </Row>
      ))}

      {canClean && safeKeys.length > 0 && (
        <Row label="reclaim">
          <span className={styles.inlineRow}>
            <Button size="sm" disabled={busy} onClick={() => doClean(safeKeys, "Clean")}>
              {busy ? "Cleaning…" : `Clean · ${formatBytes(safeSize)}`}
            </Button>
            <span className={styles.muted}>caches, logs and knowledge — always safe</span>
          </span>
        </Row>
      )}

      {canClean && destructive.map((m) => {
        const note = RECLAIM_NOTES[m.key] ?? m.label.toLowerCase();
        return (
          <Row key={m.key} label="delete">
            <span className={styles.inlineRow}>
              <Chip size="sm">{formatBytes(m.size)}</Chip>
              <span className={styles.muted}>{note}</span>
              <Button size="sm" variant="danger" disabled={busy} onClick={() => setConfirmKey(m.key)}>Delete</Button>
              <ConfirmDelete
                open={confirmKey === m.key}
                onClose={() => setConfirmKey(null)}
                onConfirm={() => { setConfirmKey(null); doClean([m.key], m.label); }}
                title={`Delete ${note}?`}
                consequence={`This permanently deletes ${note}. It cannot be undone.`}
              />
            </span>
          </Row>
        );
      })}
    </>
  );
}


export function DeleteProfileAction({ profile, onDelete, autoConfirm = false, onConsumed }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (autoConfirm) {
      setOpen(true);
      onConsumed?.();
    }
  }, [autoConfirm]);

  return (
    <span className={styles.inlineRow}>
      <Btn
        variant="ghost"
        style={{ color: "var(--c-danger)" }}
        onClick={() => setOpen(true)}
      >
        Delete profile
      </Btn>
      <span className={styles.muted}>
        moves ~/.alpi/profiles/{profile.name}/ to ~/.alpi/.trash/ — daemon
        picks up the change on its next restart
      </span>
      <ConfirmDelete
        mode="typed"
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={() => onDelete?.(profile.name)}
        title={`Delete profile @${profile.name}?`}
        consequence={`This retires the whole profile — sessions, RAG, ALP keypair, every secret stored under it. The folder is moved to ~/.alpi/.trash/ on the daemon's machine; restoring it back is a manual filesystem operation.`}
        typeToConfirm={profile.name}
        confirmLabel={`Delete @${profile.name}`}
      />
    </span>
  );
}
