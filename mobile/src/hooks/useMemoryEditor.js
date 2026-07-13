import { useCallback, useEffect, useRef, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';

export function useMemoryEditor(profile, name) {
  const { call } = useEndpoint();
  const [raw, setRaw] = useState('');
  const [rev, setRev] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const genRef = useRef(0);

  const load = useCallback(async () => {
    const gen = ++genRef.current;
    if (!profile || !name) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const r = await call('host.profile.memory_read', { profile, name });
      if (gen !== genRef.current) return;
      setRaw(r?.text ?? '');
      setRev(r?.rev ?? null);
    } catch (e) {
      if (gen !== genRef.current) return;
      setLoadError(String(e?.message || e));
      setRev(null);
    } finally {
      if (gen === genRef.current) setLoading(false);
    }
  }, [call, profile, name]);

  useEffect(() => {
    setEditing(false);
    setSaving(false);
    load();
    return () => { genRef.current += 1; };
  }, [load]);

  const canEdit = !loading && !loadError && rev != null;

  const startEdit = useCallback(() => {
    if (!canEdit) return;
    setDraft(raw);
    setEditing(true);
  }, [canEdit, raw]);

  const reload = useCallback(async () => {
    setEditing(false);
    await load();
  }, [load]);

  const save = useCallback(async ({ force = false } = {}) => {
    if (saving) return { ok: false };
    const gen = genRef.current;
    let useRev = rev;
    if (force) {
      const r = await call('host.profile.memory_read', { profile, name }).catch(() => null);
      if (!r || r.rev == null) return { ok: false, message: "couldn't read the latest version to overwrite" };
      useRev = r.rev;
    }
    if (useRev == null) return { ok: false };
    setSaving(true);
    try {
      const res = await call('host.profile.memory_write', { profile, name, text: draft, rev: useRev });
      if (gen !== genRef.current) return { ok: false, stale: true };
      setRaw(draft);
      setRev(res?.rev ?? null);
      setEditing(false);
      return { ok: true };
    } catch (e) {
      if (gen !== genRef.current) return { ok: false, stale: true };
      const message = String(e?.message || e);
      return { ok: false, conflict: message.includes('conflict'), message };
    } finally {
      if (gen === genRef.current) setSaving(false);
    }
  }, [call, profile, name, draft, rev, saving]);

  return {
    raw, rev, loading, loadError, editing, draft, setDraft,
    canEdit, saving, dirty: editing && draft !== raw,
    startEdit, cancel: () => setEditing(false), reload, save,
  };
}
