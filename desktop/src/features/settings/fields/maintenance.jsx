import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { createSwrCache } from "../../../lib/swr-cache.js";
import { useSwrValue } from "../../../hooks/useSwrValue.js";
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
