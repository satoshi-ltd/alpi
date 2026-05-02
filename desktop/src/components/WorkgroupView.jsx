import { useEffect, useMemo, useState } from "react";
import { useStickyScroll } from "../lib/useStickyScroll.js";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import Composer from "../primitives/Composer.jsx";
import Message from "../primitives/Message.jsx";
import { findLatestTask } from "../lib/workgroup-tasks.js";
import {
  loadCachedMessages,
  saveCachedMessages,
} from "../lib/workgroup-cache.js";
import styles from "./WorkgroupView.module.css";

const MY_SEQS_KEY = "alpi.workgroup.mySeqs";

function loadMySeqs(profile, wgId) {
  try {
    const raw = localStorage.getItem(`${MY_SEQS_KEY}.${profile}.${wgId}`);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveMySeqs(profile, wgId, set) {
  try {
    localStorage.setItem(
      `${MY_SEQS_KEY}.${profile}.${wgId}`,
      JSON.stringify([...set]),
    );
  } catch {}
}

export default function WorkgroupView({ workgroup, profiles, onActiveTask }) {
  const initialCached = useMemo(
    () => loadCachedMessages(workgroup.profile, workgroup.id),
    [],
  );
  const [messages, setMessages] = useState(
    initialCached.length > 0 ? initialCached : null,
  );
  const [members, setMembers] = useState([]);
  const [peers, setPeers] = useState([]);
  const [mySeqs, setMySeqs] = useState(() =>
    loadMySeqs(workgroup.profile, workgroup.id),
  );
  const [error, setError] = useState(null);
  const [costs, setCosts] = useState({});
  const scrollRef = useStickyScroll([messages]);

  const hubName = workgroup.hub_id ?? workgroup.profile;
  const hubPubkey = useMemo(
    () => profiles.find((p) => p.name === hubName)?.pubkey_b64 ?? null,
    [profiles, hubName],
  );
  const ownPubkey = useMemo(
    () =>
      profiles.find((p) => p.name === workgroup.profile)?.pubkey_b64 ?? null,
    [profiles, workgroup.profile],
  );
  const activeTask = useMemo(
    () => findLatestTask(messages, hubPubkey),
    [messages, hubPubkey],
  );

  useEffect(() => {
    onActiveTask?.(activeTask);
    return () => onActiveTask?.(null);
  }, [activeTask, onActiveTask]);

  const ownerProfile = useMemo(
    () => profiles.find((p) => p.name === hubName) ?? null,
    [profiles, hubName],
  );

  useEffect(() => {
    setMySeqs(loadMySeqs(workgroup.profile, workgroup.id));
  }, [workgroup.profile, workgroup.id]);

  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const isFirstLoad = refreshTick === 0;

    if (isFirstLoad) {
      setError(null);

      // Cost is in the raw jsonl, not in the decrypted host verb.
      invoke("read_file", {
        profile: workgroup.profile,
        relPath: `alp/workgroups/${workgroup.id}/transcript.jsonl`,
      })
        .then((text) => {
          if (cancelled) return;
          const map = {};
          for (const line of text.split("\n")) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            try {
              const entry = JSON.parse(trimmed);
              if (entry?.cost && typeof entry.seq === "number") {
                map[entry.seq] = entry.cost;
              }
            } catch {}
          }
          setCosts(map);
        })
        .catch(() => {});

      invoke("read_file", {
        profile: workgroup.profile,
        relPath: `alp/workgroups/${workgroup.id}/members.yaml`,
      })
        .then((mem) => !cancelled && setMembers(parseMembers(mem)))
        .catch(() => {});
      invoke("read_file", {
        profile: workgroup.profile,
        relPath: "alp/peers.yaml",
      })
        .then((p) => !cancelled && setPeers(parsePeers(p)))
        .catch(() => {});
    }

    invoke("workgroup_transcript", {
      profile: workgroup.profile,
      wgId: workgroup.id,
    })
      .then((rows) => {
        if (cancelled) return;
        const fresh = (rows ?? []).slice().sort((a, b) => a.seq - b.seq);
        setMessages(fresh);
        saveCachedMessages(workgroup.profile, workgroup.id, fresh);
      })
      .catch((e) => !cancelled && setError(String(e)));

    return () => {
      cancelled = true;
    };
  }, [workgroup.id, workgroup.profile, refreshTick]);

  useEffect(() => {
    const off = listen("fs-change", (event) => {
      const ev = event.payload;
      if (
        ev.kind === "workgroup_transcript" &&
        ev.profile === workgroup.profile &&
        ev.wg_id === workgroup.id
      ) {
        setRefreshTick((t) => t + 1);
      }
    });
    return () => {
      off.then((fn) => fn());
    };
  }, [workgroup.id, workgroup.profile]);

  return (
    <>
      <div ref={scrollRef} className={styles.body}>
        {error && <div className={styles.error}>{error}</div>}

        {messages && (
          <>
            {messages.length === 0 && (
              <div className={styles.empty}>No messages yet.</div>
            )}
            {messages.length > 0 && (
              <div className={styles.timeline}>
                {messages.map((m, idx) => {
                  const speaker = resolveSpeaker(m, profiles, peers, members);
                  const isFromHub = Boolean(
                    hubPubkey && m.from_pubkey === hubPubkey,
                  );
                  const isSelf = isFromHub;
                  const working = parseWorking(m.body);
                  const skip = parseSkip(m.body);
                  const done = parseDone(m.body);
                  const workingResolved =
                    working &&
                    messages
                      .slice(idx + 1)
                      .some(
                        (later) =>
                          later.from === m.from ||
                          isDoneBody(later.body),
                      );
                  let body;
                  let markdown = false;
                  if (working) {
                    body = (
                      <WorkingBody
                        reason={working.reason}
                        resolved={workingResolved}
                      />
                    );
                  } else if (skip) {
                    body = <SkipBody reason={skip.reason} />;
                  } else if (done) {
                    body = <DoneBody result={done.result} />;
                  } else {
                    body = m.body;
                    markdown = true;
                  }
                  return (
                    <Message
                      key={m.seq}
                      align={isSelf ? "right" : "left"}
                      bubble
                      accent={speaker.accent}
                      tintBubble={isFromHub}
                      header={{
                        name: speaker.name,
                        seq: m.seq,
                        time: formatCost(costs[m.seq]),
                      }}
                      body={body}
                      markdown={markdown}
                    />
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      <WorkgroupComposer
        paused={workgroup.paused}
        mentions={mentionsForWorkgroup(members, peers, profiles, ownPubkey)}
        onSend={async (text) => {
          const tempSeq = Date.now();
          const optimistic = {
            seq: tempSeq,
            from: `@${workgroup.profile}`,
            from_pubkey: ownPubkey ?? "",
            body: text,
            pending: true,
          };
          setMessages((prev) =>
            prev ? [...prev, optimistic] : [optimistic],
          );
          try {
            const result = await invoke("workgroup_post", {
              profile: workgroup.profile,
              wgId: workgroup.id,
              text,
            });
            const match = /seq\s+(\d+)/i.exec(String(result));
            if (match) {
              const seq = parseInt(match[1], 10);
              setMySeqs((prev) => {
                const next = new Set(prev);
                next.add(seq);
                saveMySeqs(workgroup.profile, workgroup.id, next);
                return next;
              });
            }
            setRefreshTick((t) => t + 1);
          } catch (e) {
            setMessages((prev) =>
              prev ? prev.filter((m) => m.seq !== tempSeq) : prev,
            );
            setError(String(e));
          }
        }}
      />
    </>
  );
}

// Parse a line-anchored `#working` marker and reason.
function parseWorking(body) {
  const m = /^[ \t]*(?:@\S+\s+)*#working(?:\s+([^\n]+))?\s*$/i.exec(
    String(body || "").split("\n")[0] ?? "",
  );
  if (!m) return null;
  return { reason: (m[1] ?? "").trim() };
}

// Parse a line-anchored `#skip` marker and reason.
function parseSkip(body) {
  const m = /^[ \t]*(?:@\S+\s+)*#skip(?:\s+([^\n]+))?\s*$/i.exec(
    String(body || "").split("\n")[0] ?? "",
  );
  if (!m) return null;
  return { reason: (m[1] ?? "").trim() };
}

// Parse a line-anchored `#done` marker and result.
function parseDone(body) {
  const m = /^[ \t]*(?:@\S+\s+)*#done\s+(.+?)\s*$/i.exec(
    String(body || "").split("\n")[0] ?? "",
  );
  if (!m) return null;
  return { result: m[1].trim() };
}

// Detect whether the line is a `#done` marker.
function isDoneBody(body) {
  return /^[ \t]*(?:@\S+\s+)*#done\b/i.test(
    String(body || "").split("\n")[0] ?? "",
  );
}

function WorkingBody({ reason, resolved }) {
  return (
    <div
      className={`${styles.working} ${resolved ? styles.workingResolved : ""}`}
    >
      <div className={styles.workingLabel}>
        {!resolved && <span className={styles.workingPulse} aria-hidden />}
        <span>working</span>
      </div>
      {reason && <div className={styles.workingReason}>{reason}</div>}
    </div>
  );
}

function SkipBody({ reason }) {
  return (
    <div className={styles.skip}>
      <div className={styles.skipLabel}>
        <span>skipped</span>
      </div>
      {reason && <div className={styles.skipReason}>{reason}</div>}
    </div>
  );
}

function DoneBody({ result }) {
  return (
    <div className={styles.done}>
      <div className={styles.doneLabel}>
        <span>done</span>
      </div>
      <div className={styles.doneResult}>{result}</div>
    </div>
  );
}

function formatCost(cost) {
  if (!cost) return null;
  const tok = typeof cost.tokens === "number" ? cost.tokens : 0;
  const usd = typeof cost.usd === "number" ? cost.usd : 0;
  const parts = [];
  if (tok > 0) {
    parts.push(tok >= 1000 ? `${(tok / 1000).toFixed(1)}K` : `${tok}`);
  }
  if (usd > 0) {
    parts.push(usd >= 0.01 ? `$${usd.toFixed(2)}` : `$${usd.toFixed(4)}`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

const PEER_PALETTE = [
  "#1877f2", "#e0245e", "#7a3ec3", "#0a84ff", "#ff6b35",
  "#30d158", "#bf5af2", "#ff9f0a", "#5e5ce6", "#64d2ff",
];

function paletteFor(seed) {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return PEER_PALETTE[Math.abs(h) % PEER_PALETTE.length];
}

function resolveSpeaker(msg, profiles, peers, members) {
  const pubkey = msg.from_pubkey || "";
  if (pubkey) {
    const matchProfile = profiles.find((p) => p.pubkey_b64 === pubkey);
    if (matchProfile) {
      return {
        name: matchProfile.name,
        accent: matchProfile.accent ?? paletteFor(matchProfile.name),
      };
    }
    const peer = peers.find((p) => p.pubkey === pubkey);
    if (peer) return { name: peer.id, accent: paletteFor(peer.id) };
    const member = members.find((m) => m.pubkey === pubkey);
    if (member?.bio) {
      return { name: member.bio, accent: paletteFor(member.bio) };
    }
  }
  const handle = String(msg.from || "").replace(/^@/, "");
  return { name: handle, accent: paletteFor(handle) };
}

// Build mention candidates for every member except self.
function mentionsForWorkgroup(members, peers, profiles, ownPubkey) {
  if (!Array.isArray(members) || members.length === 0) return [];
  const out = [];
  for (const m of members) {
    if (!m.pubkey || m.pubkey === ownPubkey) continue;
    const peer = peers.find((p) => p.pubkey === m.pubkey);
    const id = peer?.id ?? `${m.pubkey.slice(0, 12)}…`;
    const profile = profiles.find(
      (p) => p.pubkey_b64 === m.pubkey || p.name === id,
    );
    out.push({ id, accent: profile?.accent ?? null });
  }
  return out;
}


function WorkgroupComposer({ paused, mentions, onSend }) {
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);
  const hasText = text.trim().length > 0;
  const canSend = hasText && !paused && !posting;
  const placeholder = paused
    ? "Workgroup is paused"
    : posting
      ? "Posting…"
      : "Send a message — use @<peer> or #task to address";

  async function trySend() {
    if (!canSend) return;
    const payload = text.trim();
    setText("");
    setPosting(true);
    try {
      await onSend?.(payload);
    } finally {
      setPosting(false);
    }
  }

  return (
    <Composer
      value={text}
      onChange={setText}
      onSubmit={trySend}
      disabled={paused || posting}
      canSend={canSend}
      placeholder={placeholder}
      sendTitle={paused ? "Workgroup is paused" : "Send (Enter)"}
      disabledTitle="Type a message"
      mentions={mentions}
    />
  );
}

function parseMembers(text) {
  if (!text) return [];
  const out = [];
  let cur = null;
  for (const raw of text.split("\n")) {
    if (raw.startsWith("- pubkey:")) {
      if (cur) out.push(cur);
      cur = { pubkey: raw.slice("- pubkey:".length).trim() };
    } else if (cur && raw.startsWith("  ")) {
      const trimmed = raw.trim();
      const i = trimmed.indexOf(":");
      if (i > 0) {
        const k = trimmed.slice(0, i).trim();
        const v = trimmed
          .slice(i + 1)
          .trim()
          .replace(/^['"]|['"]$/g, "");
        if (k === "bio") cur.bio = v;
      }
    }
  }
  if (cur) out.push(cur);
  return out;
}

function parsePeers(text) {
  if (!text) return [];
  const out = [];
  let cur = null;
  for (const raw of text.split("\n")) {
    if (raw.startsWith("- id:")) {
      if (cur) out.push(cur);
      cur = { id: raw.slice("- id:".length).trim() };
    } else if (cur && raw.startsWith("  ")) {
      const trimmed = raw.trim();
      const i = trimmed.indexOf(":");
      if (i > 0) {
        const k = trimmed.slice(0, i).trim();
        const v = trimmed
          .slice(i + 1)
          .trim()
          .replace(/^['"]|['"]$/g, "");
        if (k === "pubkey") cur.pubkey = v;
        if (k === "alias") cur.alias = v;
      }
    }
  }
  if (cur) out.push(cur);
  return out;
}
