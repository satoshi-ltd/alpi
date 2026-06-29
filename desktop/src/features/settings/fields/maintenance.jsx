import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import { Row } from "../primitives.jsx";
import { ConfirmDelete } from "../../../primitives/index.js";
import { Btn } from "../../../primitives/index.js";
import { STORAGE_SCOPE, formatBytes } from "../util.js";
import styles from "../Settings.module.css";

function storageCacheKey(connectionId, profileName) {
  return `${connectionId || "local"}|${profileName}`;
}

const _storageCache = new Map();

export function _clearStorageCache() {
  _storageCache.clear();
}

export function StorageField({ profile, activeConnection, prefetched, onLoadingChange = null }) {
  const prefetchedMode = prefetched !== undefined;
  const key = storageCacheKey(activeConnection?.id ?? null, profile.name);
  const [items, setItems] = useState(() => (prefetchedMode ? prefetched : _storageCache.get(key) ?? null));
  const isLocal = activeConnection?.kind === "local";
  useEffect(() => {
    if (prefetchedMode) {
      setItems(prefetched);
      onLoadingChange?.(false);
      return undefined;
    }
    let cancelled = false;
    setItems(_storageCache.get(key) ?? null);
    onLoadingChange?.(true);
    invoke("profile_storage", {
      profile: profile.name,
      ...(activeConnection?.id ? { connectionId: activeConnection.id } : {}),
    })
      .then((rows) => {
        if (cancelled) return;
        const next = Array.isArray(rows) ? rows : [];
        _storageCache.set(key, next);
        setItems(next);
      })
      .catch(() => { if (!cancelled) setItems(_storageCache.get(key) ?? []); })
      .finally(() => { if (!cancelled) onLoadingChange?.(false); });
    return () => {
      cancelled = true;
      onLoadingChange?.(false);
    };
  }, [profile.name, activeConnection?.id, key, prefetchedMode, prefetched, onLoadingChange]);

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
