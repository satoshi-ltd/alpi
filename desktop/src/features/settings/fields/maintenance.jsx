import { useCallback, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { createSwrCache } from "../../../lib/swr-cache.js";
import { useSwrValue } from "../../../hooks/useSwrValue.js";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import { Row } from "../primitives.jsx";
import { ConfirmDelete, LoadFailed } from "../../../primitives/index.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { STORAGE_GROUPS, RECLAIM_NOTES, DELETE_TARGETS, formatBytes } from "../util.js";
import styles from "../Settings.module.css";
import { emptyLine } from "../../../../../common/emptyCopy.mjs";

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

  const { data: usage, error, loading, refresh: refreshUsage } = useSwrValue(
    _storageCache,
    key,
    { profile: profile.name, connectionId },
    { prefetched },
  );

  const [plan, setPlan] = useState(null);
  const [usageOverride, setUsageOverride] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const busy = busyId !== null;
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

  const doClean = useCallback(async (keys, label, id) => {
    if (busy || keys.length === 0) return;
    setBusyId(id);
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
        notify({ message: `${label}: freed ${formatBytes(freed)} · ${countLabel(removed)}`, variant: "success" });
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
      setBusyId(null);
    }
  }, [busy, profile.name, connectionId, notify, fetchPlan, onCleaned]);

  const groups = useMemo(() => {
    const live = (m) => m.size > 0 || m.count > 0;
    const known = new Set(STORAGE_GROUPS.map((g) => g.key));
    const defs = [...STORAGE_GROUPS, { key: "other", label: "Other", usage: [], desc: "everything else the daemon can clean" }];
    return defs.map((g) => {
      const usageRows = g.usage.map((k) => usageBy[k]).filter(Boolean);
      const members = (plan ?? []).filter((m) => (known.has(m.group) ? m.group : "other") === g.key && live(m));
      const safe = members.filter((m) => !m.destructive);
      return {
        key: g.key,
        label: g.label,
        desc: g.desc,
        size: usageRows.length > 0 ? usageRows.reduce((n, r) => n + r.size_bytes, 0) : members.reduce((n, r) => n + r.size, 0),
        count: usageRows.length > 0 ? usageRows.reduce((n, r) => n + r.file_count, 0) : members.reduce((n, r) => n + (r.count ?? 0), 0),
        safe,
        safeSize: safe.reduce((n, m) => n + m.size, 0),
        safeCount: safe.reduce((n, m) => n + (m.count ?? 0), 0),
        destructive: members.filter((m) => m.destructive),
      };
    }).filter((g) => g.size > 0 || g.count > 0 || g.safe.length > 0 || g.destructive.length > 0);
  }, [usageBy, plan]);

  const cleanable = groups.filter((g) => g.safe.length > 0);
  const safeKeys = cleanable.flatMap((g) => g.safe.map((m) => m.key));
  const safeSize = cleanable.reduce((n, g) => n + g.safeSize, 0);
  const safeCount = cleanable.reduce((n, g) => n + g.safeCount, 0);

  if (usageOverride == null && usage == null && !error) {
    return <Row label="storage"><span className={styles.muted}>loading…</span></Row>;
  }
  if (usageOverride == null && usage == null && error) {
    return <Row label="storage"><LoadFailed inline label="storage" onRetry={refreshUsage} /></Row>;
  }
  if (groups.length === 0) {
    return <Row label="storage"><span className={styles.muted}>{emptyLine("storage")}</span></Row>;
  }

  return (
    <>
      {groups.map((g) => (
        <Row key={g.key} label={g.label}>
          <span className={styles.inlineRow}>
            <Chip size="sm" tooltip={g.desc}>{formatBytes(g.size)}</Chip>
            <Chip size="sm">{g.count} {g.count === 1 ? "file" : "files"}</Chip>
            {canClean && g.safe.length > 0 && (
              <Button
                size="sm"
                disabled={busy}
                tip={`${formatBytes(g.safeSize)} · ${countLabel(g.safeCount)}`}
                aria-label={`Clean ${g.label.toLowerCase()} · ${formatBytes(g.safeSize)} · ${countLabel(g.safeCount)}`}
                onClick={() => doClean(g.safe.map((m) => m.key), `Clean ${g.label.toLowerCase()}`, `group:${g.key}`)}
              >
                {busyId === `group:${g.key}` ? "Cleaning…" : "Clean"}
              </Button>
            )}
            {canClean && g.destructive.map((m) => {
              const note = RECLAIM_NOTES[m.key] ?? m.label.toLowerCase();
              const target = DELETE_TARGETS[m.key] ?? m.label.toLowerCase();
              return (
                <span key={m.key} className={styles.confirmAnchor}>
                  <Button
                    size="sm"
                    variant="danger-ghost"
                    disabled={busy}
                    onClick={() => setConfirmKey(m.key)}
                  >
                    {busyId === `member:${m.key}` ? "Deleting…" : `Delete ${target}`}
                  </Button>
                  <ConfirmDelete
                    open={confirmKey === m.key}
                    onClose={() => setConfirmKey(null)}
                    onConfirm={() => { setConfirmKey(null); doClean([m.key], m.label, `member:${m.key}`); }}
                    title={`Delete ${note}?`}
                    consequence={`This permanently deletes ${note}. It cannot be undone.`}
                  />
                </span>
              );
            })}
          </span>
        </Row>
      ))}

      {canClean && cleanable.length > 1 && (
        <Row label="everything">
          <Button size="sm" disabled={busy} onClick={() => doClean(safeKeys, "Clean", "all")}>
            {busyId === "all" ? "Cleaning…" : `Clean everything safe · ${formatBytes(safeSize)} · ${countLabel(safeCount)}`}
          </Button>
        </Row>
      )}
    </>
  );
}


function countLabel(n) {
  return `${n} ${n === 1 ? "item" : "items"}`;
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
      <Button
        variant="danger-ghost"
        onClick={() => setOpen(true)}
      >
        Delete profile
      </Button>
      <span className={styles.muted}>
        moves ~/.alpi/profiles/{profile.name}/ to ~/.alpi/.trash/ — daemon
        picks up the change on its next restart
      </span>
      <ConfirmDelete
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
