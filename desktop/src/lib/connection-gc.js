import { purgeConnectionSessionTitles } from "./session-titles.js";

const exactKeys = (id) => [
  `alf:profiles:v1:${id}`,
  `alf:workgroups:v1:${id}`,
  `alf:pinned:v2:${id}`,
  `alpi:workgroup-task-cache:v3:${id}`,
];

const keyPrefixes = (id) => [
  `alpi.workgroup.cache.${id}.`,
  `alpi.session.cache.v1.${id}.`,
  `alpi.session.cache.v1.index.${id}.`,
];

export function purgeConnectionStorage(connectionId) {
  if (!connectionId || connectionId === "local") return;
  try {
    for (const key of exactKeys(connectionId)) localStorage.removeItem(key);
    const prefixes = keyPrefixes(connectionId);
    const doomed = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (key && prefixes.some((p) => key.startsWith(p))) doomed.push(key);
    }
    for (const key of doomed) localStorage.removeItem(key);
    purgeConnectionSessionTitles(connectionId);
  } catch {}
}
