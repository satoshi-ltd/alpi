import { FALLBACK_ACCENT } from '../../../common/shapes.mjs';

const localByPubkey = (summaries, pubkey) =>
  pubkey ? (summaries?.data?.profiles ?? []).find((p) => p.pubkey_b64 === pubkey) : undefined;

export function shapeForPubkey(summaries, pubkey) {
  return localByPubkey(summaries, pubkey)?.shape;
}

export function accentForPubkey(summaries, pubkey) {
  return localByPubkey(summaries, pubkey)?.accent ?? FALLBACK_ACCENT;
}
