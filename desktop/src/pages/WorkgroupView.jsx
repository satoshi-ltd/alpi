import { Fragment, memo, useEffect, useMemo, useRef, useState } from "react";
import { profileLabel } from "../lib/profile-display.js";
import { useStickyScroll } from "../lib/useStickyScroll.js";
import { useScrollProgress } from "../lib/useScrollProgress.js";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../lib/tauri-listen.js";
import { copyText } from "../lib/clipboard.js";
import { formatCostLine } from "../lib/format.js";
import { shortPubkey } from "../lib/pubkey.js";
import Composer from "../primitives/Composer.jsx";
import Message from "../primitives/Message.jsx";
import SearchBar from "../primitives/SearchBar.jsx";
import Markdown from "../primitives/Markdown.jsx";
import { setImageRoots } from "../lib/imageRoots.js";
import { useProfileDetail } from "../hooks/useProfileDetail.js";
import RelativeTime from "../primitives/RelativeTime.jsx";
import { useTranscriptSearch } from "../hooks/useTranscriptSearch.js";
import {
  classifyMessage,
  doneOutcome,
  findLatestTask,
  FOLD_CLOSED_CAP,
  parseDone,
  parseSkip,
  parseTaskOpen,
  parseWorking,
  tasksFromFold,
  validateTaskShape,
} from "../lib/workgroup-tasks.js";
import { playTts, subscribeTts, enqueueTts, voiceForPubkey } from "../lib/tts.js";
import { buildSpeakerIndex, speakerFromIndex } from "../lib/wg-speakers.js";
import { clearDraft, getDraft, setDraft } from "../lib/drafts.js";
import { useOnline } from "../lib/useOnline.js";
import {
  loadCachedMessages,
  saveCachedMessages,
} from "../lib/workgroup-cache.js";
import { fetchWorkgroupTranscript } from "../lib/workgroup-fetch.js";
import { WorkgroupChatHeader, TasksButton, Eyebrow, AlpiSilhouette } from "../primitives/index.js";
import { JumpToLatest, MarkerCard, MessageBubble } from "../primitives/index.js";
import {
  Banner,
  Chip,
  CopyIcon,
  Diamond,
  Dot,
  Icon,
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
const taskStateCache = new Map();

function taskCacheKey(connectionId, profile, wgId) {
  return `${connectionId || "local"}/${profile}/${wgId}`;
}

export function _resetTaskStateCache() {
  taskStateCache.clear();
}

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
  onGone,
  onOpenSettings,
  onReload,
  daemonOffline = false,
  searchOpen = false,
  onCloseSearch,
  taskHistoryOpenTick = 0,
  refreshCommandTick = 0,
  pauseCommandTick = 0,
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
  const taskKey = taskCacheKey(connectionId, workgroup.profile, workgroup.id);
  const [taskState, setTaskState] = useState(() => taskStateCache.get(taskKey) ?? null);
  const [taskStateStale, setTaskStateStale] = useState(false);
  const taskTargetRef = useRef(taskKey);
  const taskRequestRef = useRef(0);
  const taskAcceptedRef = useRef(0);
  const scrollRef = useStickyScroll([messages]);
  const refreshMountedRef = useRef(false);
  const pauseMountedRef = useRef(false);
  const { farFromBottom, scrollToBottom } = useScrollProgress(scrollRef);
  const search = useTranscriptSearch(scrollRef, searchOpen);
  const closeSearch = () => {
    search.reset();
    onCloseSearch?.();
  };

  useEffect(() => {
    taskTargetRef.current = taskKey;
    return () => {
      if (taskTargetRef.current === taskKey) taskTargetRef.current = null;
    };
  }, [taskKey]);

  // Resolve inline images against the workgroup profile's workspace (project assets).
  const { detail: wgDetail } = useProfileDetail(connectionId ?? null, workgroup.profile ?? null);
  useEffect(() => {
    setImageRoots([wgDetail?.workspace]);
  }, [wgDetail?.workspace]);
  useEffect(() => {
    setPeers(Array.isArray(wgDetail?.peers) ? wgDetail.peers : []);
  }, [wgDetail?.peers]);

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
  const localTask = useMemo(
    () => findLatestTask(messages, hubPubkey),
    [messages, hubPubkey],
  );
  const blocked = taskState?.blocked ?? null;
  const blockedReason = useMemo(() => {
    if (!blocked) return "";
    const slug = blocked.slug || "";
    return (blocked.reason || "")
      .replace(/^\s*blocked\b/i, "")
      .replace(new RegExp(`^\\s*${slug}\\b`, "i"), "")
      .replace(/^[\s·:—-]+/, "")
      .trim();
  }, [blocked]);
  const run = taskState?.pipeline_run ?? null;
  const hostActive = taskState?.active ?? null;
  const foldedTasks = useMemo(() => tasksFromFold(taskState), [taskState]);
  // The local derivation only sees the loaded tail, so it is the fallback, never a second answer.
  const activeTask = useMemo(() => {
    if (taskState == null) return localTask;
    if (hostActive == null) return null;
    return {
      slug: hostActive.slug ?? null,
      text: hostActive.title ?? "",
      seq: hostActive.opened_seq ?? null,
      state: "open",
      result: null,
    };
  }, [taskState, hostActive, localTask]);
  const loadedSeqs = useMemo(
    () => new Set((messages ?? []).map((m) => m.seq)),
    [messages],
  );
  // A `#working` is stale once superseded — either by a later post from the same author, or by the hub's `#done` that closes the task. A member `#skip` is a per-peer pass, not a close, so it never marks others' `#working` stale. Scope resets when we cross a `#task` boundary going backwards.
  const workingStale = useMemo(() => {
    const set = new Set();
    if (!messages || messages.length === 0) return set;
    let seenAuthor = new Set();
    let taskClosed = false;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      const fromHub = !hubPubkey || m.from_pubkey === hubPubkey;
      if (fromHub && parseDone(m.body)) taskClosed = true;
      if (parseWorking(m.body)) {
        if (seenAuthor.has(m.from_pubkey) || taskClosed) set.add(m.seq);
      }
      if (fromHub && parseTaskOpen(m.body)) {
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
  const speakerIndex = useMemo(
    () => buildSpeakerIndex(profiles, peers, members),
    [profiles, peers, members],
  );

  const autoRead = !!workgroup.auto_read;
  const lastReadSeqRef = useRef(-1);
  const autoReadWgRef = useRef(null);
  // baseline on the first LOADED message set so existing history is never auto-read
  useEffect(() => {
    if (messages == null) return;
    const maxSeq = messages.reduce((a, m) => Math.max(a, m.seq ?? -1), -1);
    if (autoReadWgRef.current !== workgroup.id) {
      autoReadWgRef.current = workgroup.id;
      lastReadSeqRef.current = maxSeq;
      return;
    }
    if (!autoRead) {
      lastReadSeqRef.current = maxSeq;
      return;
    }
    const fresh = messages
      .filter((m) => (m.seq ?? -1) > lastReadSeqRef.current
        && m.from_pubkey !== ownPubkey && m.body)
      .sort((a, b) => a.seq - b.seq);
    if (fresh.length) {
      lastReadSeqRef.current = maxSeq;
      for (const m of fresh) {
        enqueueTts({
          key: `wg:${workgroup.id}:${m.seq}`,
          profile: workgroup.profile,
          voice: voiceMap[m.from_pubkey] || voiceForPubkey(m.from_pubkey),
          text: m.body,
          accent: speakerFromIndex(speakerIndex, m)?.accent,
        });
      }
    }
  }, [messages, autoRead, workgroup.id, workgroup.profile, ownPubkey, voiceMap, speakerIndex]);
  const bumpRefresh = () => {
    setRefreshBeat((b) => b + 1);
    setRefreshTick((t) => t + 1);
  };

  const togglePause = async () => {
    try {
      await invoke("workgroup_action", {
        profile: workgroup.profile,
        wgId: workgroup.id,
        action: workgroup.paused ? "resume" : "pause",
        ...(connectionId ? { connectionId } : {}),
      });
      onReload?.();
      setRefreshTick((t) => t + 1);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    if (!refreshMountedRef.current) {
      refreshMountedRef.current = true;
      return;
    }
    if (refreshCommandTick > 0) bumpRefresh();
  }, [refreshCommandTick]);

  useEffect(() => {
    if (!pauseMountedRef.current) {
      pauseMountedRef.current = true;
      return;
    }
    if (pauseCommandTick > 0) togglePause();
  }, [pauseCommandTick]);

  useEffect(() => {
    let cancelled = false;
    setError(null);

    invoke("workgroup_members", {
      profile: workgroup.profile,
      wgId: workgroup.id,
      ...(connectionId ? { connectionId } : {}),
    })
      .then((rows) => !cancelled && setMembers(Array.isArray(rows) ? rows : []))
      .catch(() => {});

    const taskRequest = taskRequestRef.current + 1;
    taskRequestRef.current = taskRequest;
    invoke("workgroup_tasks", {
      profile: workgroup.profile,
      wgId: workgroup.id,
      ...(connectionId ? { connectionId } : {}),
    })
      .then((res) => {
        if (taskTargetRef.current !== taskKey || taskRequest < taskAcceptedRef.current) return;
        const next = res && typeof res === "object" ? res : null;
        taskAcceptedRef.current = taskRequest;
        if (next) taskStateCache.set(taskKey, next);
        else taskStateCache.delete(taskKey);
        setTaskState(next);
        setTaskStateStale(false);
      })
      .catch(() => {
        if (taskTargetRef.current === taskKey) setTaskStateStale(true);
      });

    fetchWorkgroupTranscript(connectionId, workgroup.profile, workgroup.id)
      .then((rows) => {
        if (cancelled) return;
        const fresh = (rows ?? []).slice().sort((a, b) => a.seq - b.seq);
        setMessages(fresh);
        saveCachedMessages(connectionId, workgroup.profile, workgroup.id, fresh);
      })
      .catch((e) => {
        if (cancelled) return;
        if (String(e).includes("-32004")) {
          onGone?.(connectionId || "local", workgroup.profile, workgroup.id);
          return;
        }
        setError(String(e));
      });

    return () => {
      cancelled = true;
    };
  }, [workgroup.id, workgroup.profile, refreshTick, connectionId, onGone]);

  useEffect(() => {
    let cancelled = false;
    let unlistenFs = null;
    let unlistenDaemon = null;
    let bumpTimer = null;
    // Coalesce post bursts so the task fold and transcript refresh once per beat.
    const bump = () => {
      if (bumpTimer) return;
      bumpTimer = setTimeout(() => {
        bumpTimer = null;
        if (!cancelled) setRefreshTick((t) => t + 1);
      }, 200);
    };
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
        (kind === "wg.post" || kind === "wg.done" || kind === "wg.task"
          || kind === "wg.skip" || kind === "workgroup_changed") &&
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
      if (bumpTimer) clearTimeout(bumpTimer);
      safeUnlisten(unlistenFs);
      safeUnlisten(unlistenDaemon);
    };
  }, [workgroup.id, workgroup.profile, connectionId]);

  const jumpToSeq = (seq) => {
    if (seq == null) return;
    const el = document.getElementById(`task-${seq}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const banners = (blocked || workgroup.paused || taskStateStale) && (
    <>
      {taskStateStale && (
        <Banner kind="warning">
          <span data-testid="pipeline-stale">
            <strong>Workgroup state unavailable.</strong> The daemon did not answer, so the
            phase strip and the blocked banner may be out of date.
          </span>
        </Banner>
      )}
      {blocked && (
        <Banner kind="danger" pulsing>
          <span className={styles.blockedLine}>
            <strong>Blocked at #{blocked.slug}.</strong>
            {blockedReason ? ` ${blockedReason}` : ""}
          </span>
        </Banner>
      )}
      {workgroup.paused && (
        <Banner kind="warning" pulsing>
          <strong>This workgroup is paused.</strong> New messages won't fire. Resume from the header.
        </Banner>
      )}
    </>
  );

  return (
    <>
      <WorkgroupChatHeader
        workgroup={workgroup}
        hubAccent={ownerProfile?.accent}
        hubName={hubName}
        hubBio={ownerProfile?.bio || ownerProfile?.public_bio}
        memberCount={members.length || workgroup.members || 0}
        budget={
          workgroup.budget_usd > 0
            ? { used: workgroup.spent_usd ?? 0, cap: workgroup.budget_usd }
            : null
        }
        paused={!!workgroup.paused}
        onTogglePause={togglePause}
        autoRead={!!workgroup.auto_read}
        onToggleAutoRead={async () => {
          try {
            await invoke("workgroup_update", {
              profile: workgroup.profile,
              wgId: workgroup.id,
              autoRead: !workgroup.auto_read,
              ...(connectionId ? { connectionId } : {}),
            });
            onReload?.();
          } catch (e) {
            setError(String(e));
          }
        }}
        onOpenSettings={onOpenSettings ? () => onOpenSettings(workgroup) : undefined}
        onRefresh={bumpRefresh}
        tasksButton={
          <TasksButton
            thread={messages ?? []}
            tasks={foldedTasks}
            historyCapped={(taskState?.closed?.length ?? 0) >= FOLD_CLOSED_CAP}
            hubColor={ownerProfile?.accent}
            hubPubkey={hubPubkey}
            openTick={taskHistoryOpenTick}
            onJump={(taskId) => {
              const el = document.getElementById(`task-${taskId}`);
              if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
          />
        }
      />
      {banners}
      {taskState == null && workgroup.pipeline_mode && (
        <div className={styles.pipeline} data-testid="pipeline-loading">
          <Eyebrow className={styles.pipelineLabel}>pipeline</Eyebrow>
          <Chip size="sm" ghost icon={<SpinnerIcon />}>Loading flow…</Chip>
        </div>
      )}
      {run && Array.isArray(run.phases) && run.phases.length > 0 && (
        <div className={styles.pipeline}>
          <Eyebrow className={styles.pipelineLabel}>pipeline · {run.pipeline}</Eyebrow>
          {run.phases.map((p, i) => {
            const state = phaseVisual(p, run.status);
            const canJump = p.seq != null && loadedSeqs.has(p.seq);
            const tip = canJump
              ? [`Jump to #${p.slug}`, state === "current" ? hostActive?.title : null]
                .filter(Boolean).join(" · ")
              : phaseUnavailable(p);
            return (
              <Fragment key={p.slug}>
                {i > 0 && <span className={styles.pipelineSep} aria-hidden>›</span>}
                <span
                  className={`${styles.phase} ${state === "skipped" ? styles.phaseSkipped : ""}`.trim()}
                  data-phase={p.slug}
                  data-phase-state={state}
                  title={canJump ? undefined : tip}
                  aria-disabled={canJump ? undefined : "true"}
                >
                  <Chip
                    size="sm"
                    ghost={state !== "blocked"}
                    state={state === "blocked" ? "error" : undefined}
                    icon={state === "pending" ? undefined : <PhaseIcon state={state} accent={ownerProfile?.accent} />}
                    tooltip={canJump ? tip || undefined : undefined}
                    onClick={canJump ? () => jumpToSeq(p.seq) : undefined}
                    disabled={!canJump}
                  >
                    #{p.slug}
                  </Chip>
                </span>
              </Fragment>
            );
          })}
          {RUN_STATUS[run.status] && (
            <Chip size="sm" state={RUN_STATUS[run.status]}>{runStatusText(run.status)}</Chip>
          )}

        </div>
      )}
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
                <AlpiSilhouette color={ownerProfile?.accent || "var(--accent)"} />
                <div className={styles.emptyHeading}>no posts yet</div>
                <div className={styles.emptyModel}>direct @{profileLabel(hubName)} to open a #task</div>
              </div>
            )}
            {messages.length > 0 && (
              <div className={styles.timeline}>
                {messages.map((m) => {
                  const speaker = speakerFromIndex(speakerIndex, m);
                  const cost = m.cost;
                  const ttsKey = `wg:${workgroup.id}:${m.seq}`;
                  return (
                    <WgMessage
                      key={m.seq}
                      seq={m.seq}
                      body={m.body}
                      at={m.at}
                      isFromHub={Boolean(hubPubkey && m.from_pubkey === hubPubkey)}
                      speakerName={speaker.name}
                      speakerAccent={speaker.accent}
                      speakerBio={speaker.bio}
                      costTokens={cost?.tokens ?? 0}
                      costUsd={cost?.usd ?? 0}
                      stale={workingStale.has(m.seq)}
                      ttsKey={ttsKey}
                      ttsKind={ttsState?.key === ttsKey ? ttsState.kind : null}
                      online={online}
                      voice={voiceMap[m.from_pubkey] || voiceForPubkey(m.from_pubkey)}
                      profile={workgroup.profile}
                    />
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
        paused={workgroup.paused}
        offline={daemonOffline}
        draftKey={`wg|${connectionId || "local"}|${workgroup.profile}|${workgroup.id}`}
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
              ...(connectionId ? { connectionId } : {}),
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

function renderWgFooter({
  plainText, at, styles, ttsKey, profile, voice, ttsKind, online,
}) {
  const isLoading = ttsKind === "loading";
  const isPlaying = ttsKind === "playing";
  const ttsDisabled = !online && !isPlaying;
  const tipText = !online && !isPlaying
    ? "Offline — TTS unavailable"
    : isLoading ? "Loading…" : isPlaying ? "Stop" : "Read aloud";
  // Workgroup `at` is an ISO string; RelativeTime expects unix seconds.
  const stampTs = at ? Date.parse(at) / 1000 : 0;
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
      {stampTs ? (
        <Mono className={`tnum ${styles.footerTime}`}><RelativeTime ts={stampTs} /></Mono>
      ) : null}
    </>
  );
}

const PHASE_ICON = {
  completed: { name: "check", color: "var(--c-success)" },
  skipped: { name: "x", color: "var(--c-warning)" },
  blocked: { name: "ban", color: "var(--c-danger)" },
};

const RUN_STATUS = {
  blocked: "error",
  completed: "on",
  between: "off",
};

const RUN_STATUS_TEXT = {
  running: "running",
  between: "between phases",
  blocked: "blocked",
  completed: "completed",
};

function runStatusText(status) {
  return RUN_STATUS_TEXT[status] ?? "unfinished";
}

function phaseUnavailable(phase) {
  if (phase.seq == null) {
    return `#${phase.slug} has not opened yet — nothing to jump to`;
  }
  return `#${phase.slug} opened at post #${phase.seq}, outside the loaded history`;
}

// A blocked run keeps its phase `current`; the strip shows that phase as the block.
function phaseVisual(phase, status) {
  return status === "blocked" && phase.state === "current" ? "blocked" : phase.state;
}

function PhaseIcon({ state, accent }) {
  if (state === "current") return <Dot pulse color={accent || "var(--accent)"} />;
  const def = PHASE_ICON[state];
  return def ? <Icon name={def.name} size="xs" color={def.color} /> : null;
}

function renderWgMeta({ seq, cost, speaker, isFromHub, styles }) {
  const rawDiamond = <Diamond color={speaker.accent} />;
  const diamond = speaker.bio
    ? <Tip text={speaker.bio} side={isFromHub ? "up-r" : "up-l"}>{rawDiamond}</Tip>
    : rawDiamond;
  const peer = (
    <span className={styles.metaGroup}>
      {!isFromHub && diamond}
      <span className={styles.speakerName}>{speaker.name}</span>
      {isFromHub && diamond}
    </span>
  );
  const seqEl = <Mono className="tnum">{`#${seq}`}</Mono>;
  const hasCost = (cost?.tokens ?? 0) > 0 || (cost?.usd ?? 0) > 0;
  const costEl = hasCost ? <Mono className="tnum">{formatCostLine(cost)}</Mono> : null;
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

// Scalar props only — every transcript refetch rebuilds the message objects, so the memo must survive identity churn.
const WgMessage = memo(function WgMessage({
  seq,
  body,
  at,
  isFromHub,
  speakerName,
  speakerAccent,
  speakerBio,
  costTokens,
  costUsd,
  stale,
  ttsKey,
  ttsKind,
  online,
  voice,
  profile,
}) {
  const speaker = { name: speakerName, accent: speakerAccent, bio: speakerBio };
  const cls = classifyMessage(body);
  const task = cls.variant === "task" ? cls.task : null;
  const working = cls.variant === "working" ? { content: cls.text } : null;
  const skip = cls.variant === "skip" ? { content: cls.text } : null;
  const done = cls.variant === "done" ? { content: cls.text } : null;

  const cost = costTokens > 0 || costUsd > 0
    ? { tokens: costTokens, usd: costUsd }
    : null;
  const meta = renderWgMeta({ seq, cost, speaker, isFromHub, styles });
  const speakableText = task
    ? task.content
    : (working?.content || skip?.content || done?.content || body);
  const footer = renderWgFooter({
    plainText: speakableText,
    at,
    styles,
    ttsKey,
    profile,
    voice,
    ttsKind,
    online,
  });

  if (task) {
    return (
      <MarkerCard
        variant="task"
        side={isFromHub ? "right" : "left"}
        taskId={seq}
        hubColor={speaker.accent}
        meta={meta}
        footer={footer}
      >
        {task.content ? (
          <Markdown as="div" className="alpi-md" source={task.content} />
        ) : null}
      </MarkerCard>
    );
  }

  if (working || skip || done) {
    const variant = working ? "working" : skip ? "skip" : "done";
    const isStale = Boolean(working && stale);
    const content = (working || skip || done).content;
    return (
      <MarkerCard
        variant={variant}
        outcome={done ? doneOutcome(body) : null}
        stale={isStale}
        side={isFromHub ? "right" : "left"}
        taskId={seq}
        hubColor={speaker.accent}
        meta={meta}
        footer={footer}
      >
        {content ? (
          <Markdown as="div" className="alpi-md" source={content} />
        ) : null}
      </MarkerCard>
    );
  }

  return (
    <MessageBubble
      side={isFromHub ? "right" : "left"}
      tint={speaker.accent}
      meta={meta}
      footer={footer}
    >
      <Markdown as="div" className="alpi-md" source={body} />
    </MessageBubble>
  );
});

function mentionsForWorkgroup(members, peers, profiles, ownPubkey) {
  if (!Array.isArray(members) || members.length === 0) return [];
  const out = [];
  for (const m of members) {
    if (!m.pubkey || m.pubkey === ownPubkey) continue;
    const peer = peers.find((p) => p.pubkey === m.pubkey);
    const id = peer?.id ?? shortPubkey(m.pubkey, 12);
    const profile = profiles.find(
      (p) => p.pubkey_b64 === m.pubkey || p.name === id,
    );
    out.push({ id, accent: profile?.accent ?? null });
  }
  return out;
}

function WorkgroupComposer({ paused, offline, mentions, onSend, hubName, hubAccent, draftKey }) {
  const [text, setText] = useState(() => getDraft(draftKey));
  useEffect(() => {
    setText(getDraft(draftKey));
  }, [draftKey]);
  const updateText = (next) => {
    setText(next);
    setDraft(draftKey, next);
  };
  const [posting, setPosting] = useState(false);
  const hasText = text.trim().length > 0;
  const taskShape = validateTaskShape(text);
  const canSend = hasText && !paused && !offline && !posting && taskShape.ok;
  const placeholder = paused
    ? "Workgroup is paused"
    : offline
      ? "Reconnecting — you can keep typing…"
      : posting
        ? "Posting…"
        : "Send a message — use @<peer> or #task #<slug> to open";

  async function trySend() {
    if (!canSend) return;
    const payload = text.trim();
    setText("");
    clearDraft(draftKey);
    setPosting(true);
    try {
      await onSend?.(payload);
    } finally {
      setPosting(false);
    }
  }

  const hint = !taskShape.ok ? (
    <span className={styles.metaGroup} style={{ color: "var(--c-warning)" }}>
      {taskShape.error}
    </span>
  ) : (
    <>
      <span className={styles.metaGroup}>
        <span className={styles.hintArrow}>→</span>
        <Diamond color={hubAccent} />
        <span>
          <Mono className={styles.hintMono}>@{profileLabel(hubName)}</Mono>
          {" formulates as "}
          <Mono className={styles.hintMono}>#task #&lt;slug&gt;</Mono>
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
      onChange={updateText}
      onSubmit={trySend}
      disabled={paused || posting}
      canSend={canSend}
      accent={hubAccent ?? null}
      placeholder={placeholder}
      sendTitle={paused ? "Workgroup is paused" : offline ? "Reconnecting…" : "Send (⌘↵)"}
      disabledTitle={
        taskShape.ok ? "Type a message" : "#task needs a #<slug>"
      }
      mentions={mentions}
      hint={hint}
    />
  );
}
