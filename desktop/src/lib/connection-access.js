export function connectionCanManage(connections, connectionId) {
  const connection = (connections ?? []).find((c) => c.id === connectionId);
  return !!connection && (connection.kind === "local" || connection.role !== "member");
}
