// Daemon host.voice.preview → base64 mp3 → expo-audio. One preview at a time (matches desktop stopTts).

import { createAudioPlayer, setAudioModeAsync } from 'expo-audio';

let currentPlayer = null;
let currentVoiceId = null;
const listeners = new Set();

export function subscribeVoicePreview(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify(state) {
  for (const fn of [...listeners]) {
    try { fn(state); } catch { /* swallow */ }
  }
}

export function currentlyPlayingVoice() {
  return currentVoiceId;
}

export function stopVoicePreview() {
  if (currentPlayer) {
    try { currentPlayer.pause(); } catch { /* */ }
    try { currentPlayer.remove(); } catch { /* */ }
    currentPlayer = null;
  }
  if (currentVoiceId) {
    const id = currentVoiceId;
    currentVoiceId = null;
    notify({ kind: 'stopped', voiceId: id });
  }
}

// playsInSilentMode: deliberate user action shouldn't be swallowed by ringer switch.
let audioModeReady = false;
async function ensureAudioMode() {
  if (audioModeReady) return;
  try {
    await setAudioModeAsync({ playsInSilentMode: true });
    audioModeReady = true;
  } catch { /* iOS falls back to silent-mode rules */ }
}

export async function playVoicePreview({ call, voiceId }) {
  if (!call || !voiceId) return;
  // Re-tap same voice while loading/playing → stop (implicit cancel affordance).
  if (currentVoiceId === voiceId) {
    stopVoicePreview();
    return;
  }
  stopVoicePreview();
  currentVoiceId = voiceId;
  notify({ kind: 'loading', voiceId });

  let result;
  try {
    result = await call('host.voice.preview', { voice_id: voiceId });
  } catch (e) {
    if (currentVoiceId !== voiceId) return;
    currentVoiceId = null;
    notify({ kind: 'error', voiceId, error: String(e) });
    return;
  }
  if (currentVoiceId !== voiceId) return; // user moved on while we were synth'ing

  const b64 = result?.audio_b64;
  if (!b64) {
    currentVoiceId = null;
    notify({ kind: 'error', voiceId, error: 'empty audio' });
    return;
  }

  await ensureAudioMode();
  // expo-audio accepts data URI directly — avoids expo-file-system for <30KB preview clips.
  const uri = `data:${result.mime ?? 'audio/mpeg'};base64,${b64}`;
  try {
    const player = createAudioPlayer({ uri });
    currentPlayer = player;
    notify({ kind: 'playing', voiceId });
    player.addListener('playbackStatusUpdate', (status) => {
      if (status.didJustFinish) {
        if (currentPlayer === player) {
          currentPlayer = null;
          const id = currentVoiceId;
          currentVoiceId = null;
          notify({ kind: 'stopped', voiceId: id });
        }
        try { player.remove(); } catch { /* */ }
      }
    });
    player.play();
  } catch (e) {
    currentPlayer = null;
    currentVoiceId = null;
    notify({ kind: 'error', voiceId, error: String(e) });
  }
}
