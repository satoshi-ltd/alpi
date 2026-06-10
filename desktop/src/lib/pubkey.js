export function shortPubkey(pubkey, length = 16) {
  return `${(pubkey || "").slice(0, length)}…`;
}

export function pubkeyTail(pubkey) {
  return `…${(pubkey || "").slice(-7)}`;
}
