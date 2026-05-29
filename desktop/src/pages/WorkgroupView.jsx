import { useEffect, useMemo, useState } from "react";
import { useStickyScroll } from "../lib/useStickyScroll.js";
import { useScrollProgress } from "../lib/useScrollProgress.js";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../lib/tauri-listen.js";
import Composer from "../primitives/Composer.jsx";
import Message from "../primitives/Message.jsx";
import SearchBar from "../primitives/SearchBar.jsx";
import { renderMarkdown } from "../lib/markdown.js";
import { useTranscriptSearch } from "../hooks/useTranscriptSearch.js";
import {
  findLatestTask,
  parseDone,
  parseSkip,
  parseTaskOpen,
  parseWorking,
} from "../lib/workgroup-tasks.js";
import { playTts, subscribeTts, voiceForPubkey } from "../lib/tts.js";
import { useOnline } from "../lib/useOnline.js";
import {
  loadCachedMessages,
  saveCachedMessages,
} from "../lib/workgroup-cache.js";
import { fetchWorkgroupTranscript } from "../lib/workgroup-fetch.js";
import { WorkgroupChatHeader, TasksButton } from "../primitives/index.js";
import { JumpToLatest, MarkerCard, MessageBubble } from "../primitives/index.js";
import {
  Banner,
  CopyIcon,
  Diamond,
  IconBtn,
  Kbd,
  Mono,
  RefreshBar,
  SpinnerIcon,
  StopIcon,
  Tip,
  VolumeIcon,
} from "../primitives/index.js";
import styles from "./WorkgroupView.module.css";

const MY_SEQS_KEY = "alpi.workgroup.mySeqs";

function mySeqsKey(connectionId, profile, wgId) {
  return `${MY_SEQS_KEY}.${connectionId || "local"}.${profile}.${wgId}`;
}

function loadMySeqs(connectionId, profile, wgId) {
  try {
    const raw = localStorage.getItem(mySeqsKey(connectionId, profile, wgId));
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveMySeqs(connectionId, profile, wgId, set) {
  try {
    localStorage.setItem(
      mySeqsKey(connectionId, profile, wgId),
      JSON.stringify([...set]),
    );
  } catch {}
}

export default function WorkgroupView({
  workgroup,
  profiles,
  connectionId,
  onActiveTask,
  onOpenSettings,
  onReload,
  daemonOffline = false,
  searchOpen = false,
  onCloseSearch,
}) {
  const initialCached = useMemo(
    () => loadCachedMessages(connectionId, workgroup.profile, workgroup.id),
    [connectionId, workgroup.profile, workgroup.id],
  );
  const [messages, setMessages] = useState(
    initialCached.length > 0 ? initialCached : null,
  );
  const [members, setMembers] = useState([]);
  const [peers, setPeers] = useState([]);
  const [mySeqs, setMySeqs] = useState(() =>
    loadMySeqs(connectionId, workgroup.profile, workgroup.id),
  );
  const [error, setError] = useState(null);
  const [costs, setCosts] = useState({});
  const scrollRef = useStickyScroll([messages]);
  const { farFromBottom, scrollToBottom } = useScrollProgress(scrollRef);
  const search = useTranscriptSearch(scrollRef, searchOpen);
  const closeSearch = () => {
    search.reset();
    onCloseSearch?.();
  };

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
  // A `#working` is stale once superseded — either by a later post from the same author, or by a `#done`/`#skip` that closes the task. Scope resets when we cross a `#task` boundary going backwards.
  const workingStale = useMemo(() => {
    const set = new Set();
    if (!messages || messages.length === 0) return set;
    let seenAuthor = new Set();
    let taskClosed = false;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (parseDone(m.body) || parseSkip(m.body)) taskClosed = true;
      if (parseWorking(m.body)) {
        if (seenAuthor.has(m.from_pubkey) || taskClosed) set.add(m.seq);
      }
      if (parseTaskOpen(m.body)) {
        seenAuthor = new Set();
        taskClosed = false;
      }
      seenAuthor.add(m.from_pubkey);
    }
    return set;
  }, [messages]);
  useEffect(() => {
    onActiveTask?.(activeTask);
    return () => onActiveTask?.(null);
  }, [activeTask, onActiveTask]);

  const ownerProfile = useMemo(
    () => profiles.find((p) => p.name === hubName) ?? null,
    [profiles, hubName],
  );

  useEffect(() => {
    setMySeqs(loadMySeqs(connectionId, workgroup.profile, workgroup.id));
  }, [connectionId, workgroup.profile, workgroup.id]);

  const [refreshTick, setRefreshTick] = useState(0);
  const [refreshBeat, setRefreshBeat] = useState(0);
  const [ttsState, setTtsState] = useState(null);
  useEffect(() => subscribeTts(setTtsState), []);
  const online = useOnline();
  const voiceMap = useMemo(() => {
    const out = {};
    for (const m of members) {
      if (m.pubkey && m.voice) out[m.pubkey] = m.voice;
    }
    return out;
  }, [members]);
  const bumpRefresh = () => {
    setRefreshBeat((b) => b + 1);
    setRefreshTick((t) => t + 1);
  };

  useEffect(() => {
    let cancelled = false;
    setError(null);

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

    fetchWorkgroupTranscript(connectionId, workgroup.profile, workgroup.id)
      .then((rows) => {
        if (cancelled) return;
        const fresh = (rows ?? []).slice().sort((a, b) => a.seq - b.seq);
        setMessages(fresh);
        saveCachedMessages(connectionId, workgroup.profile, workgroup.id, fresh);
      })
      .catch((e) => !cancelled && setError(String(e)));

    return () => {
      cancelled = true;
    };
  }, [workgroup.id, workgroup.profile, refreshTick, connectionId]);

  useEffect(() => {
    let cancelled = false;
    let unlistenFs = null;
    let unlistenDaemon = null;
    const bump = () => setRefreshTick((t) => t + 1);
    listen("fs-change", (event) => {
      const ev = event.payload;
      if (
        ev.kind === "workgroup_transcript" &&
        ev.profile === workgroup.profile &&
        ev.wg_id === workgroup.id
      ) bump();
    })
      .then((fn) => {
        if (cancelled) safeUnlisten(fn);
        else unlistenFs = fn;
      })
      .catch(() => {});
    // Remote daemons have no local fs watcher — daemon-event is the canonical refresh signal for the transcript.
    listen("daemon-event", (event) => {
      const payload = event.payload ?? {};
      // Drop frames from a daemon that's not the active one (late arrival after switch).
      if (payload.connection_id && payload.connection_id !== connectionId) return;
      const frame = payload.frame ?? payload;
      const kind = frame?.event;
      const data = frame?.data ?? {};
      if (
        (kind === "wg.post" || kind === "wg.done" || kind === "wg.task" || kind === "wg.skip") &&
        data.profile === workgroup.profile &&
        data.wg_id === workgroup.id
      ) bump();
    })
      .then((fn) => {
        if (cancelled) safeUnlisten(fn);
        else unlistenDaemon = fn;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      safeUnlisten(unlistenFs);
      safeUnlisten(unlistenDaemon);
    };
  }, [workgroup.id, workgroup.profile, connectionId]);

  return (
    <>
      {workgroup.paused && (
        <Banner kind="warning" pulsing>
          This workgroup is paused. New messages won't fire. Resume from the header.
        </Banner>
      )}
      <WorkgroupChatHeader
        workgroup={workgroup}
        hubAccent={ownerProfile?.accent}
        hubName={hubName}
        memberCount={members.length || workgroup.members || 0}
        budget={
          workgroup.budget_usd > 0
            ? { used: workgroup.spent_usd ?? 0, cap: workgroup.budget_usd }
            : null
        }
        paused={!!workgroup.paused}
        onTogglePause={async () => {
          try {
            await invoke("workgroup_action", {
              profile: workgroup.profile,
              wgId: workgroup.id,
              action: workgroup.paused ? "resume" : "pause",
            });
            onReload?.();
            setRefreshTick((t) => t + 1);
          } catch (e) {
            setError(String(e));
          }
        }}
        onOpenSettings={onOpenSettings ? () => onOpenSettings(workgroup) : undefined}
        onRefresh={bumpRefresh}
        tasksButton={
          <TasksButton
            thread={messages ?? []}
            hubColor={ownerProfile?.accent}
            onJump={(taskId) => {
              const el = document.getElementById(`task-${taskId}`);
              if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
          />
        }
      />
      {searchOpen && (
        <SearchBar
          query={search.query}
          setQuery={search.setQuery}
          total={search.total}
          currentIndex={search.currentIndex}
          onNext={search.next}
          onPrev={search.prev}
          onClose={closeSearch}
        />
      )}
      <div className={styles.bodyWrap}>
      <div
        ref={scrollRef}
        className={styles.body}
      >
        <RefreshBar
          key={refreshBeat}
          active={refreshBeat > 0}
          accent={ownerProfile?.accent ?? null}
        />
        {error && <div className={styles.error}>{error}</div>}

        {messages && (
          <>
            {messages.length === 0 && (
              <div className={styles.empty}>
                <span className={styles.emptyHash} aria-hidden>
                  #
                </span>
                <span>no posts yet · direct @{hubName} to open a #task</span>
              </div>
            )}
            {messages.length > 0 && (
              <div className={styles.timeline}>
                {messages.map((m) => {
                  const speaker = resolveSpeaker(m, profiles, peers, members);
                  const isFromHub = Boolean(
                    hubPubkey && m.from_pubkey === hubPubkey,
                  );
                  const task = parseTaskOpen(m.body);
                  const working = parseWorking(m.body);
                  const skip = parseSkip(m.body);
                  const done = parseDone(m.body);

                  const meta = renderWgMeta({
                    seq: m.seq,
                    cost: costs[m.seq],
                    speaker,
                    isFromHub,
                    styles,
                  });
                  const speakableText = task
                    ? task.content
                    : (working?.content || skip?.content || done?.content || m.body);
                  const footer = renderWgFooter({
                    plainText: speakableText,
                    styles,
                    ttsKey: `wg:${workgroup.id}:${m.seq}`,
                    profile: workgroup.profile,
                    voice: voiceMap[m.from_pubkey]
                      || voiceForPubkey(m.from_pubkey),
                    ttsState,
                    online,
                  });

                  if (task) {
                    return (
                      <MarkerCard
                        key={m.seq}
                        variant="task"
                        side={isFromHub ? "right" : "left"}
                        taskId={m.seq}
                        hubColor={speaker.accent}
                        meta={meta}
                        footer={footer}
                      >
                        {task.content ? (
                          <div
                            className="alpi-md"
                            dangerouslySetInnerHTML={{
                              __html: renderMarkdown(task.content),
                            }}
                          />
                        ) : null}
                      </MarkerCard>
                    );
                  }

                  if (working || skip || done) {
                    const variant = working ? "working" : skip ? "skip" : "done";
                    const isStale = working && workingStale.has(m.seq);
                    const content = (working || skip || done).content;
                    return (
                      <MarkerCard
                        key={m.seq}
                        variant={variant}
                        label={isStale ? "WORK" : undefined}
                        stale={isStale}
                        side={isFromHub ? "right" : "left"}
                        taskId={m.seq}
                        hubColor={speaker.accent}
                        meta={meta}
                        footer={footer}
                      >
                        {content ? (
                          <div
                            className="alpi-md"
                            dangerouslySetInnerHTML={{
                              __html: renderMarkdown(content),
                            }}
                          />
                        ) : null}
                      </MarkerCard>
                    );
                  }

                  return (
                    <MessageBubble
                      key={m.seq}
                      side={isFromHub ? "right" : "left"}
                      tint={speaker.accent}
                      meta={meta}
                      footer={footer}
                    >
                      <span
                        className="alpi-md"
                        dangerouslySetInnerHTML={{
                          __html: renderMarkdown(m.body),
                        }}
                      />
                    </MessageBubble>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
        <JumpToLatest show={farFromBottom} onClick={scrollToBottom} />
      </div>

      <WorkgroupComposer
        paused={workgroup.paused || daemonOffline}
        mentions={mentionsForWorkgroup(members, peers, profiles, ownPubkey)}
        hubName={hubName}
        hubAccent={ownerProfile?.accent}
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
                saveMySeqs(connectionId, workgroup.profile, workgroup.id, next);
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

function formatCost(cost) {
  const tok = typeof cost?.tokens === "number" ? cost.tokens : 0;
  const usd = typeof cost?.usd === "number" ? cost.usd : 0;
  const tokStr = tok >= 1000 ? `${(tok / 1000).toFixed(1)}K` : `${tok}`;
  const usdStr = usd >= 0.01 ? `$${usd.toFixed(2)}` : `$${usd.toFixed(4)}`;
  return `${tokStr} · ${usdStr}`;
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text || "");
  } catch { /* */ }
}

function renderWgFooter({
  plainText, styles, ttsKey, profile, voice, ttsState, online,
}) {
  const ttsKind = ttsState?.key === ttsKey ? ttsState.kind : null;
  const isLoading = ttsKind === "loading";
  const isPlaying = ttsKind === "playing";
  const ttsDisabled = !online && !isPlaying;
  const tipText = !online && !isPlaying
    ? "Offline — TTS unavailable"
    : isLoading ? "Loading…" : isPlaying ? "Stop" : "Read aloud";
  return (
    <>
      <Tip text="Copy" side="up">
        <IconBtn
          aria-label="Copy message"
          onClick={() => copyText(plainText)}
          className={styles.footerBtn}
        >
          <CopyIcon style={{ width: 13, height: 13 }} />
        </IconBtn>
      </Tip>
      <Tip text={tipText} side="up">
        <IconBtn
          aria-label={tipText}
          disabled={ttsDisabled}
          onClick={() => playTts({
            key: ttsKey,
            profile,
            voice,
            text: plainText,
          })}
          className={styles.footerBtn}
        >
          {isLoading ? (
            <SpinnerIcon style={{ width: 13, height: 13 }} />
          ) : isPlaying ? (
            <StopIcon style={{ width: 13, height: 13 }} />
          ) : (
            <VolumeIcon style={{ width: 13, height: 13 }} />
          )}
        </IconBtn>
      </Tip>
    </>
  );
}

function renderWgMeta({ seq, cost, speaker, isFromHub, styles }) {
  const peer = (
    <span className={styles.metaGroup}>
      {!isFromHub && <Diamond color={speaker.accent} />}
      <span className={styles.speakerName}>{speaker.name}</span>
      {isFromHub && <Diamond color={speaker.accent} />}
    </span>
  );
  const seqEl = <Mono className="tnum">{`#${seq}`}</Mono>;
  const costEl = <Mono className="tnum">{formatCost(cost)}</Mono>;
  return isFromHub ? (
    <>
      {costEl}
      {seqEl}
      {peer}
    </>
  ) : (
    <>
      {peer}
      {seqEl}
      {costEl}
    </>
  );
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

function WorkgroupComposer({ paused, mentions, onSend, hubName, hubAccent }) {
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

  const hint = (
    <>
      <span className={styles.metaGroup}>
        <span className={styles.hintArrow}>→</span>
        <Diamond color={hubAccent} />
        <span>
          <Mono className={styles.hintMono}>@{hubName}</Mono>
          {" formulates as "}
          <Mono className={styles.hintMono}>#task</Mono>
        </span>
      </span>
      <span className={styles.kbdGroup}>
        <Kbd>⌘</Kbd>
        <Kbd>↵</Kbd>
        <span>send</span>
      </span>
    </>
  );

  return (
    <Composer
      value={text}
      onChange={setText}
      onSubmit={trySend}
      disabled={paused || posting}
      canSend={canSend}
      accent={hubAccent ?? null}
      placeholder={placeholder}
      sendTitle={paused ? "Workgroup is paused" : "Send (⌘↵)"}
      disabledTitle="Type a message"
      mentions={mentions}
      hint={hint}
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
        else if (k === "voice") cur.voice = v;
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
