import { invoke } from "@tauri-apps/api/core";

export const VOICE_POOL = [
  "en-US-AriaNeural",
  "en-US-GuyNeural",
  "en-US-JennyNeural",
  "en-GB-SoniaNeural",
  "en-GB-RyanNeural",
  "en-AU-NatashaNeural",
  "en-AU-WilliamNeural",
  "es-ES-ElviraNeural",
  "es-ES-AlvaroNeural",
  "es-MX-DaliaNeural",
  "fr-FR-DeniseNeural",
  "fr-FR-HenriNeural",
  "de-DE-KatjaNeural",
  "it-IT-ElsaNeural",
  "pt-BR-FranciscaNeural",
];

export function voiceForPubkey(pubkey) {
  if (!pubkey) return VOICE_POOL[0];
  let h = 0;
  for (let i = 0; i < pubkey.length; i++) {
    h = (h * 31 + pubkey.charCodeAt(i)) | 0;
  }
  return VOICE_POOL[Math.abs(h) % VOICE_POOL.length];
}

const EMOJI_RE = /[\u{1F000}-\u{1FAFF}\u{2190}-\u{21FF}\u{2300}-\u{23FF}\u{2460}-\u{24FF}\u{2500}-\u{25FF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{3030}\u{303D}\u{203C}\u{2049}\u{FE0F}\u{200D}\u{20E3}]+/gu;

export function stripMarkdown(md) {
  if (!md) return "";
  let s = String(md);
  s = s.replace(/```[\s\S]*?```/g, " ");
  s = s.replace(/`([^`]+)`/g, "$1");
  s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  s = s.replace(/https?:\/\/(?:www\.)?([^\s/)]+)\S*/g, "$1");
  s = s.replace(/^\s{0,3}#{1,6}\s+/gm, "");
  s = s.replace(/^\s{0,3}>\s?/gm, "");
  s = s.replace(/^\s*[-*+]\s+/gm, "");
  s = s.replace(/^\s*\d+\.\s+/gm, "");
  s = s.replace(/(\*\*|__)(.*?)\1/g, "$2");
  s = s.replace(/(\*|_)(.*?)\1/g, "$2");
  s = s.replace(/~~(.*?)~~/g, "$1");
  s = s.replace(EMOJI_RE, " ");
  s = s.replace(/\|/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

export async function scriptFor(profile, text) {
  const fallback = stripMarkdown(text);
  if (!profile || !fallback) return fallback;
  try {
    const script = String((await invoke("voice_script", { profile, text })) || "").trim();
    return script || fallback;
  } catch {
    return fallback;
  }
}

let currentAudio = null;
let currentKey = null;
let currentAccent = null;
const subs = new Set();

function notify(state) {
  for (const fn of subs) {
    try { fn(state); } catch { /* */ }
  }
  if (state?.kind === "error") {
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("alpi-tts-error", { detail: state }),
      );
    }
    console.error("[tts] failed", state);
  }
}

export function subscribeTts(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

export function currentlyPlayingKey() {
  return currentKey;
}

export function isTtsActive() {
  return Boolean(currentKey);
}

export function stopTts() {
  if (currentAudio) {
    try { currentAudio.pause(); } catch { /* */ }
    try { URL.revokeObjectURL(currentAudio.src); } catch { /* */ }
    currentAudio = null;
  }
  if (currentKey) {
    const k = currentKey;
    currentKey = null;
    notify({ kind: "stopped", key: k });
  }
}

const queue = [];
let draining = false;

function playTtsAwait(item) {
  return new Promise((resolve) => {
    const unsub = subscribeTts((state) => {
      if (state?.key !== item.key) return;
      if (state.kind === "stopped" || state.kind === "error" || state.kind === "skipped") {
        unsub();
        resolve();
      }
    });
    Promise.resolve(playTts(item)).catch(() => {
      unsub();
      resolve();
    });
  });
}

async function drain() {
  draining = true;
  while (queue.length) {
    await playTtsAwait(queue.shift());
  }
  draining = false;
}

export function enqueueTts(item) {
  if (!stripMarkdown(item?.text)) return;
  queue.push(item);
  if (!draining) drain();
}

export function clearTtsQueue() {
  queue.length = 0;
  stopTts();
}

const FALLBACK_VOICE = "en-US-AriaNeural";

const PREVIEW_PHRASES = {
  en: "Hello, I'm Alpi.",
  es: "Hola, soy Alpi.",
  fr: "Bonjour, je suis Alpi.",
  de: "Hallo, ich bin Alpi.",
  it: "Ciao, sono Alpi.",
  pt: "Olá, sou Alpi.",
};

export function previewPhraseFor(voiceId) {
  const lang = (voiceId || "").split("-", 1)[0].toLowerCase();
  return PREVIEW_PHRASES[lang] || PREVIEW_PHRASES.en;
}

async function synth(_profile, voice, text) {
  return invoke("tts_synthesize", { voice, text });
}

// Restarting the SAME key spawns a new chain with the same currentKey — only the generation token tells the live chain from the aborted one.
let playGen = 0;

export async function playTts({ key, profile, voice, text, accent = null, raw = false }) {
  const clean = stripMarkdown(text);
  if (!clean) {
    notify({ kind: "skipped", key });
    return;
  }

  if (currentKey === key) {
    // re-click a loading key is ignored so a click can't cancel its own synth
    if (currentAudio) stopTts();
    else notify({ kind: "skipped", key });
    return;
  }
  stopTts();
  const gen = ++playGen;
  currentKey = key;
  currentAccent = accent;
  notify({ kind: "loading", key, accent });

  const spoken = raw ? clean : await scriptFor(profile, text);
  if (playGen !== gen || currentKey !== key) return;

  let b64;
  try {
    b64 = await synth(profile, voice, spoken);
  } catch (e) {
    if (voice && voice !== FALLBACK_VOICE) {
      try {
        b64 = await synth(profile, FALLBACK_VOICE, spoken);
      } catch (e2) {
        if (playGen !== gen) return;
        currentKey = null;
        notify({ kind: "error", key, error: String(e2) });
        return;
      }
    } else {
      if (playGen !== gen) return;
      currentKey = null;
      notify({ kind: "error", key, error: String(e) });
      return;
    }
  }
  if (playGen !== gen || currentKey !== key) return;
  if (!b64) {
    currentKey = null;
    notify({ kind: "error", key, error: "empty audio" });
    return;
  }

  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], { type: "audio/mpeg" });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.onended = () => {
    if (currentAudio === audio) {
      URL.revokeObjectURL(url);
      currentAudio = null;
      const k = currentKey;
      currentKey = null;
      notify({ kind: "stopped", key: k });
    }
  };
  audio.onerror = () => {
    if (currentAudio === audio) {
      URL.revokeObjectURL(url);
      currentAudio = null;
      const k = currentKey;
      currentKey = null;
      notify({ kind: "error", key: k, error: "playback failed" });
    }
  };
  currentAudio = audio;
  try {
    await audio.play();
    if (currentAudio !== audio) return;
    notify({ kind: "playing", key, accent: currentAccent });
  } catch (e) {
    URL.revokeObjectURL(url);
    if (currentAudio !== audio) return;
    currentAudio = null;
    currentKey = null;
    notify({ kind: "error", key, error: String(e) });
  }
}
