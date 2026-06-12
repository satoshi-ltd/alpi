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

export function stripMarkdown(md) {
  if (!md) return '';
  let s = String(md);
  s = s.replace(/```[\s\S]*?```/g, ' ');
  s = s.replace(/`([^`]+)`/g, '$1');
  s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1');
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
  s = s.replace(/^\s{0,3}#{1,6}\s+/gm, '');
  s = s.replace(/^\s{0,3}>\s?/gm, '');
  s = s.replace(/^\s*[-*+]\s+/gm, '');
  s = s.replace(/^\s*\d+\.\s+/gm, '');
  s = s.replace(/(\*\*|__)(.*?)\1/g, '$2');
  s = s.replace(/(\*|_)(.*?)\1/g, '$2');
  s = s.replace(/~~(.*?)~~/g, '$1');
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

async function playOne({ call, key, voiceId, text, accent = null }) {
  const clean = stripMarkdown(text);
  if (!clean) return;
  stopReadAloud();
  currentKey = key;
  notify({ kind: 'loading', key, accent });

  let result;
  try {
    result = await call('host.voice.preview', { voice_id: voiceId, text: clean });
  } catch (e) {
    if (currentKey !== key) return;
    currentKey = null;
    notify({ kind: 'error', key, error: String(e) });
    return;
  }
  if (currentKey !== key) return;

  const b64 = result?.audio_b64;
  if (!b64) {
    currentKey = null;
    notify({ kind: 'error', key, error: 'empty audio' });
    return;
  }

  await ensureAudioMode();
  if (currentKey !== key) return;  // stopped during synth/audio-mode setup
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
      currentPlayer = null;
      currentKey = null;
      notify({ kind: 'error', key, error: String(e) });
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
