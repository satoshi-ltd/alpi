import { invoke } from "@tauri-apps/api/core";

// In-flight transcripts keyed by (connection, profile, wg_id). When two listeners (App.jsx + WorkgroupView) react to the same wg.post in the same tick they share a single round-trip.
const inflight = new Map();
// Cursor cache so wg.post triggers incremental fetches (after_seq) instead of repulling the whole window. Per (connection, profile, wg_id) — never reuse across daemons. Cleared on connection change by ``invalidateTranscriptCache``.
const cursors = new Map();
// Merged posts cache so consumers can append-only on incremental fetches.
const cache = new Map();

function makeKey(connectionId, profile, wgId) {
  return `${connectionId || "local"}|${profile}|${wgId}`;
}

// Exported for tests; merge is the bug-prone bit (dedupe + sort) and deserves direct coverage.
export function mergeByseq(prev, next) {
  if (!prev || prev.length === 0) return next;
  if (!next || next.length === 0) return prev;
  const seen = new Set(prev.map((p) => p.seq));
  const append = next.filter((p) => !seen.has(p.seq));
  if (append.length === 0) return prev;
  return [...prev, ...append].sort((a, b) => (a.seq || 0) - (b.seq || 0));
}

export function fetchWorkgroupTranscript(connectionId, profile, wgId, options = {}) {
  const key = makeKey(connectionId, profile, wgId);
  const existing = inflight.get(key);
  if (existing) return existing;
  // First fetch: tail=true ships only the most recent window (~200) — for a 10k-post workgroup that's the difference between snappy and seconds-long over Tailscale. Subsequent fetches use after_seq.
  const afterSeq = options.afterSeq ?? cursors.get(key) ?? null;
  const payload = afterSeq != null
    ? { profile, wgId, afterSeq, limit: options.limit ?? 200 }
    : { profile, wgId, tail: true, limit: options.limit ?? 200 };
  if (connectionId) payload.connectionId = connectionId;
  const promise = invoke("workgroup_transcript", payload)
    .then((res) => {
      const posts = Array.isArray(res?.posts) ? res.posts : Array.isArray(res) ? res : [];
      const nextSeq = res?.next_seq;
      const merged = mergeByseq(cache.get(key), posts);
      cache.set(key, merged);
      if (typeof nextSeq === "number" && nextSeq > (cursors.get(key) || 0)) {
        cursors.set(key, nextSeq);
      } else if (posts.length > 0) {
        const max = posts[posts.length - 1].seq;
        if (typeof max === "number" && max > (cursors.get(key) || 0)) {
          cursors.set(key, max);
        }
      }
      return merged;
    })
    .finally(() => {
      inflight.delete(key);
    });
  inflight.set(key, promise);
  return promise;
}

// Test-only: drop every cache + cursor. App code never needs this.
export function _resetTranscriptCachesForTests() {
  inflight.clear();
  cursors.clear();
  cache.clear();
}

export function invalidateTranscriptCache(connectionId) {
  // Clear when active connection changes — a remote alpi must never see another daemon's cached posts.
  const prefix = `${connectionId || "local"}|`;
  for (const k of Array.from(cursors.keys())) {
    if (k.startsWith(prefix)) cursors.delete(k);
  }
  for (const k of Array.from(cache.keys())) {
    if (k.startsWith(prefix)) cache.delete(k);
  }
}

export function invalidateWorkgroupTranscriptCache(connectionId, profile, wgId) {
  const key = makeKey(connectionId, profile, wgId);
  cursors.delete(key);
  cache.delete(key);
}
