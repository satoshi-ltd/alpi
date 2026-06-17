export function autoReadText(streamedReply, turns) {
  const last = Array.isArray(turns) ? turns[turns.length - 1] : null;
  return streamedReply || last?.assistant || "";
}

export function consumeAutoRead(streamedReply, autoRead, turns) {
  return { speak: autoRead ? autoReadText(streamedReply, turns) : "", nextStreamed: "" };
}
