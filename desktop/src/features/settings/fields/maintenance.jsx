import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { createSwrCache } from "../../../lib/swr-cache.js";
import { useSwrValue } from "../../../hooks/useSwrValue.js";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import { Row } from "../primitives.jsx";
import { ConfirmDelete } from "../../../primitives/index.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Btn } from "../../../primitives/index.js";
import { STORAGE_SCOPE, formatBytes } from "../util.js";
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

export function StorageField({ profile, activeConnection, prefetched, onLoadingChange = null }) {
  const connectionId = activeConnection?.id ?? null;
  const key = storageCacheKey(connectionId, profile.name);
  const { data, error, loading } = useSwrValue(
    _storageCache,
    key,
    { profile: profile.name, connectionId },
    { prefetched },
  );
  const items = data ?? (error ? [] : null);
  const isLocal = activeConnection?.kind === "local";

  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);
  useEffect(() => () => onLoadingChange?.(false), [onLoadingChange]);

  const visible = (items ?? []).filter(
    (it) => it.size_bytes > 0 || it.file_count > 0,
  );

  if (items === null) {
    return (
      <Row label="size">
        <span className={styles.muted}>loading…</span>
      </Row>
    );
  }

  if (visible.length === 0) {
    return (
      <Row label="size">
        <span className={styles.muted}>nothing yet</span>
      </Row>
    );
  }

  return (
    <>
      {visible.map((it) => (
        <Row key={it.key} label={it.label}>
          <span className={styles.inlineRow}>
            <Chip size="sm" tooltip={STORAGE_SCOPE[it.key]}>
              {formatBytes(it.size_bytes)}
            </Chip>
            <Chip size="sm">
              {it.file_count} {it.file_count === 1 ? "file" : "files"}
            </Chip>
            {isLocal && (
              <Button
                size="sm"
                onClick={() => invoke("reveal_in_finder", { path: it.path })}
              >
                Reveal
              </Button>
            )}
          </span>
        </Row>
      ))}
    </>
  );
}

export function CleanupField({ profile, activeConnection, onCleaned }) {
  const notify = useNotify();
  const connectionId = activeConnection?.id ?? null;
  const [plan, setPlan] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const [confirmKey, setConfirmKey] = useState(null);

  const fetchPlan = () =>
    invoke("cleanup_plan", {
      profile: profile.name,
      ...(connectionId ? { connectionId } : {}),
    })
      .then((rows) => setPlan(Array.isArray(rows) ? rows : []))
      .catch(() => setPlan("error"));

  useEffect(() => {
    setPlan(null);
    setConfirmKey(null);
    fetchPlan();
  }, [profile.name, connectionId]);

  const doClean = async (cat) => {
    setBusyKey(cat.key);
    try {
      const results = await invoke("cleanup_apply", {
        profile: profile.name,
        keys: [cat.key],
        ...(connectionId ? { connectionId } : {}),
      });
      const rows = Array.isArray(results) ? results : [];
      const failed = rows.filter((r) => !r.ok);
      const removed = rows.reduce((n, r) => n + (r.removed ?? 0), 0);
      const freed = rows.reduce((n, r) => n + (r.freed_bytes ?? 0), 0);
      if (failed.length > 0) {
        notify({
          message: `${cat.label}: ${failed[0].errors?.[0] ?? "cleanup failed"}`,
          variant: "error",
          duration: 4000,
        });
      } else {
        notify({ message: `${cat.label}: freed ${formatBytes(freed)}`, variant: "success" });
      }
      await fetchPlan();
      if (removed > 0) onCleaned?.();
    } catch (e) {
      notify({ message: `${cat.label}: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusyKey(null);
    }
  };

  const clean = (cat) => {
    if (cat.destructive) {
      setConfirmKey(cat.key);
      return;
    }
    doClean(cat);
  };

  if (plan === null) {
    return (
      <Row label="cleanup">
        <span className={styles.muted}>loading…</span>
      </Row>
    );
  }
  if (plan === "error") {
    return (
      <Row label="cleanup">
        <span className={styles.muted}>
          cleanup unavailable — daemon offline or older than 0.10.24
        </span>
      </Row>
    );
  }
  const reclaimable = plan.filter((c) => c.size > 0);
  if (reclaimable.length === 0) {
    return (
      <Row label="cleanup">
        <span className={styles.muted}>nothing to clean</span>
      </Row>
    );
  }
  return (
    <>
      {reclaimable.map((c) => (
        <Row key={c.key} label={c.label.toLowerCase()}>
          <span className={styles.inlineRow}>
            <Chip size="sm" tooltip={c.desc}>{formatBytes(c.size)}</Chip>
            <Chip size="sm">{c.count} {c.count === 1 ? "item" : "items"}</Chip>
            <Button
              size="sm"
              variant={c.destructive ? "danger" : "ghost"}
              disabled={busyKey !== null}
              onClick={() => clean(c)}
            >
              {busyKey === c.key
                ? "Cleaning…"
                : c.action === "vacuum" ? "Compact" : "Clean"}
            </Button>
            <ConfirmDelete
              open={confirmKey === c.key}
              onClose={() => setConfirmKey(null)}
              onConfirm={() => {
                setConfirmKey(null);
                doClean(c);
              }}
              title={`Delete ${c.label.toLowerCase()}?`}
              consequence={`${c.desc}. This cannot be undone.`}
            />
          </span>
        </Row>
      ))}
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
        removes ~/.alpi/profiles/{profile.name}/ — daemon picks up the
        change on its next restart
      </span>
      <ConfirmDelete
        mode="typed"
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={() => onDelete?.(profile.name)}
        title={`Delete profile @${profile.name}?`}
        consequence={`This wipes ~/.alpi/profiles/${profile.name}/ on disk — sessions, RAG, ALP keypair, every secret stored under it. Cannot be undone.`}
        typeToConfirm={profile.name}
        confirmLabel={`Delete @${profile.name}`}
      />
    </span>
  );
}
