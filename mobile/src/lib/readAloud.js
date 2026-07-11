import { createAudioPlayer, setAudioModeAsync } from 'expo-audio';

let currentPlayer = null;
let currentKey = null;
let currentResolve = null;
const listeners = new Set();

export function subscribeReadAloud(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify(state) {
  for (const fn of [...listeners]) {
    try { fn(state); } catch { /* swallow */ }
  }
}

export function currentlyReadingKey() {
  return currentKey;
}

export function stopReadAloud() {
  if (currentPlayer) {
    try { currentPlayer.pause(); } catch { /* */ }
    try { currentPlayer.remove(); } catch { /* */ }
    currentPlayer = null;
  }
  if (currentKey) {
    const k = currentKey;
    currentKey = null;
    notify({ kind: 'stopped', key: k });
  }
  // unblock a playOne awaiting didJustFinish so the FIFO drain never stalls
  if (currentResolve) {
    const r = currentResolve;
    currentResolve = null;
    r();
  }
}

const EMOJI_RE = /[\u{1F000}-\u{1FAFF}\u{2190}-\u{21FF}\u{2300}-\u{23FF}\u{2460}-\u{24FF}\u{2500}-\u{25FF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{3030}\u{303D}\u{203C}\u{2049}\u{FE0F}\u{200D}\u{20E3}]+/gu;

export function stripMarkdown(md) {
  if (!md) return '';
  let s = String(md);
  s = s.replace(/```[\s\S]*?```/g, ' ');
  s = s.replace(/`([^`]+)`/g, '$1');
  s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1');
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
  s = s.replace(/https?:\/\/(?:www\.)?([^\s/)]+)\S*/g, '$1');
  s = s.replace(/^\s{0,3}#{1,6}\s+/gm, '');
  s = s.replace(/^\s{0,3}>\s?/gm, '');
  s = s.replace(/^\s*[-*+]\s+/gm, '');
  s = s.replace(/^\s*\d+\.\s+/gm, '');
  s = s.replace(/(\*\*|__)(.*?)\1/g, '$2');
  s = s.replace(/(\*|_)(.*?)\1/g, '$2');
  s = s.replace(/~~(.*?)~~/g, '$1');
  s = s.replace(EMOJI_RE, ' ');
  s = s.replace(/\|/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

let audioModeReady = false;
async function ensureAudioMode() {
  if (audioModeReady) return;
  try {
    await setAudioModeAsync({ playsInSilentMode: true });
    audioModeReady = true;
  } catch { /* iOS falls back to silent-mode rules */ }
}

// Restarting the SAME key spawns a new chain with the same currentKey — only the generation token tells the live chain from the aborted one.
let playGen = 0;

async function playOne({ call, key, voiceId, text, accent = null, profile = null }) {
  const clean = stripMarkdown(text);
  if (!clean) return;
  stopReadAloud();
  const gen = ++playGen;
  currentKey = key;
  notify({ kind: 'loading', key, accent });

  let spoken = clean;
  if (profile) {
    try {
      const res = await call('host.voice.script', { profile, text });
      const script = String(res?.script || '').trim();
      if (script) spoken = script;
    } catch { /* older daemon or offline — the local strip is the audio */ }
    if (playGen !== gen || currentKey !== key) return;
  }

  let result;
  try {
    result = await call('host.voice.preview', { voice_id: voiceId, text: spoken });
  } catch (e) {
    if (playGen !== gen || currentKey !== key) return;
    currentKey = null;
    notify({ kind: 'error', key, error: String(e) });
    return;
  }
  if (playGen !== gen || currentKey !== key) return;

  const b64 = result?.audio_b64;
  if (!b64) {
    currentKey = null;
    notify({ kind: 'error', key, error: 'empty audio' });
    return;
  }

  await ensureAudioMode();
  if (playGen !== gen || currentKey !== key) return;  // stopped during synth/audio-mode setup
  const uri = `data:${result.mime ?? 'audio/mpeg'};base64,${b64}`;
  await new Promise((resolve) => {
    const done = () => {
      if (currentResolve === resolve) currentResolve = null;
      resolve();
    };
    try {
      const player = createAudioPlayer({ uri });
      currentPlayer = player;
      currentResolve = resolve;
      notify({ kind: 'playing', key, accent });
      player.addListener('playbackStatusUpdate', (status) => {
        if (status.didJustFinish && currentPlayer === player) {
          currentPlayer = null;
          currentKey = null;
          notify({ kind: 'stopped', key });
          try { player.remove(); } catch { /* */ }
          done();
        }
      });
      player.play();
    } catch (e) {
      if (playGen === gen) {
        currentPlayer = null;
        currentKey = null;
        notify({ kind: 'error', key, error: String(e) });
      }
      done();
    }
  });
}

const queue = [];
let draining = false;

async function drain() {
  draining = true;
  while (queue.length) {
    await playOne(queue.shift());
  }
  draining = false;
}

export function enqueueReadAloud(item) {
  if (!stripMarkdown(item?.text)) return;
  queue.push(item);
  if (!draining) drain();
}

export function clearReadAloud() {
  queue.length = 0;
  stopReadAloud();
}
