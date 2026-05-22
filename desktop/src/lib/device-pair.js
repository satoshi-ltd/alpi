export function resolveCancelAction(devices, tokenId, typedLabel) {
  if (!tokenId) return { kind: "noop" };
  const list = Array.isArray(devices) ? devices : [];
  const row = list.find((d) => d && d.token_id === tokenId);
  if (row && row.last_seen) {
    const label = (typedLabel ?? "").trim() || "Unnamed device";
    return { kind: "keep", label };
  }
  return { kind: "revoke" };
}
