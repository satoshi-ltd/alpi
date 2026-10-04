import { FALLBACK_ACCENT } from '../../../common/folds.mjs';

const localByPubkey = (summaries, pubkey) =>
  pubkey ? (summaries?.data?.profiles ?? []).find((p) => p.pubkey_b64 === pubkey) : undefined;

export function foldForPubkey(summaries, pubkey) {
  return localByPubkey(summaries, pubkey)?.fold;
}

export function accentForPubkey(summaries, pubkey) {
  return localByPubkey(summaries, pubkey)?.accent ?? FALLBACK_ACCENT;
}
