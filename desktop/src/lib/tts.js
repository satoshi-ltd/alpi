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

export function stripMarkdown(md) {
  if (!md) return "";
  let s = String(md);
  s = s.replace(/```[\s\S]*?```/g, " ");
  s = s.replace(/`([^`]+)`/g, "$1");
  s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  s = s.replace(/^\s{0,3}#{1,6}\s+/gm, "");
  s = s.replace(/^\s{0,3}>\s?/gm, "");
  s = s.replace(/^\s*[-*+]\s+/gm, "");
  s = s.replace(/^\s*\d+\.\s+/gm, "");
  s = s.replace(/(\*\*|__)(.*?)\1/g, "$2");
  s = s.replace(/(\*|_)(.*?)\1/g, "$2");
  s = s.replace(/~~(.*?)~~/g, "$1");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

let currentAudio = null;
let currentKey = null;
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

export async function playTts({ key, profile, voice, text }) {
  const clean = stripMarkdown(text);
  if (!clean) return;

  if (currentKey === key) {
    // Re-click on a still-loading key is ignored on purpose so an impatient click can't cancel its own synth.
    if (currentAudio) stopTts();
    return;
  }
  stopTts();
  currentKey = key;
  notify({ kind: "loading", key });

  let b64;
  try {
    b64 = await synth(profile, voice, clean);
  } catch (e) {
    if (voice && voice !== FALLBACK_VOICE) {
      try {
        b64 = await synth(profile, FALLBACK_VOICE, clean);
      } catch (e2) {
        currentKey = null;
        notify({ kind: "error", key, error: String(e2) });
        return;
      }
    } else {
      currentKey = null;
      notify({ kind: "error", key, error: String(e) });
      return;
    }
  }
  if (currentKey !== key) return;
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
    notify({ kind: "playing", key });
  } catch (e) {
    URL.revokeObjectURL(url);
    if (currentAudio !== audio) return;
    currentAudio = null;
    currentKey = null;
    notify({ kind: "error", key, error: String(e) });
  }
}
