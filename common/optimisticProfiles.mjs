let clock = 0;
let version = 0;
const stacks = new Map();
const lanes = new Map();
const queued = new Set();
const listeners = new Set();

const profileKey = (connectionId, name) => `${connectionId || "local"}|${name}`;
const slotKey = (key, path) => `${key}\u0000${path}`;
const covers = (outer, inner) => inner === outer || inner.startsWith(`${outer}.`);

function changed() {
  version += 1;
  for (const fn of listeners) fn();
}

export function editClock() {
  return clock;
}

export function beginEdit(connectionId, name, patch) {
  const key = profileKey(connectionId, name);
  const seq = ++clock;
  const paths = Object.keys(patch);
  const prefix = `${key}\u0000`;
  for (const slot of Array.from(stacks.keys())) {
    if (!slot.startsWith(prefix)) continue;
    const other = slot.slice(prefix.length);
    if (paths.some((path) => path !== other && covers(path, other))) stacks.delete(slot);
  }
  for (const ticket of queued) {
    if (ticket.key !== key) continue;
    for (const old of ticket.paths) {
      if (paths.some((path) => covers(path, old))) ticket.replaced.add(old);
    }
  }
  for (const path of paths) {
    const slot = slotKey(key, path);
    const stack = stacks.get(slot) ?? [];
    stack.push({ key, path, value: patch[path], seq, confirmedAt: null });
    stacks.set(slot, stack);
  }
  changed();
  return { key, seq, paths, replaced: new Set() };
}

function topIs(ticket) {
  return ticket.paths.some((path) => stacks.get(slotKey(ticket.key, path))?.at(-1)?.seq === ticket.seq);
}

export function confirmEdit(ticket) {
  const latest = topIs(ticket);
  const at = ++clock;
  for (const path of ticket.paths) {
    const entry = stacks.get(slotKey(ticket.key, path))?.find((e) => e.seq === ticket.seq);
    if (entry) entry.confirmedAt = at;
  }
  return latest;
}

function dropTicket(ticket) {
  for (const path of ticket.paths) {
    const slot = slotKey(ticket.key, path);
    const stack = (stacks.get(slot) ?? []).filter((e) => e.seq !== ticket.seq);
    if (stack.length) stacks.set(slot, stack);
    else stacks.delete(slot);
  }
}

export function failEdit(ticket) {
  const latest = topIs(ticket);
  dropTicket(ticket);
  changed();
  return latest;
}

function dropTop(slot, keep) {
  const stack = stacks.get(slot);
  const top = stack?.at(-1);
  if (!top || top.confirmedAt == null || keep(top)) return false;
  stacks.delete(slot);
  return true;
}

function hasConfirmedSurvivor(ticket) {
  return ticket.paths.some((path) => stacks.get(slotKey(ticket.key, path))?.at(-1)?.confirmedAt != null);
}

export function releaseConfirmed(connectionId, since, owns = () => true) {
  const prefix = `${connectionId || "local"}|`;
  let any = false;
  for (const slot of Array.from(stacks.keys())) {
    if (!slot.startsWith(prefix)) continue;
    any = dropTop(slot, (top) => top.confirmedAt > since || !owns(top.key.slice(prefix.length), top.path)) || any;
  }
  if (any) changed();
}

export const DETAIL_ONLY_FIELDS = ["tiers", "vision_model", "model_reasoning_effort"];

export function releaseLanded(connectionId, since, profiles, fields = null) {
  if (!Array.isArray(profiles) || stacks.size === 0) return;
  const rows = new Map(profiles.filter((p) => p?.name).map((p) => [p.name, p]));
  releaseConfirmed(connectionId, since, (name, path) => {
    const row = rows.get(name);
    const top = path.split(".")[0];
    return !!row && top in row && (!fields || fields.includes(top));
  });
}

function setPath(target, path, value) {
  const [head, ...rest] = path.split(".");
  if (!rest.length) return { ...target, [head]: value };
  const child = target?.[head] && typeof target[head] === "object" ? target[head] : {};
  return { ...target, [head]: setPath(child, rest.join("."), value) };
}

function editsFor(key) {
  const out = [];
  const prefix = `${key}\u0000`;
  for (const [slot, stack] of stacks) {
    if (slot.startsWith(prefix) && stack.length) out.push(stack.at(-1));
  }
  return out.sort((a, b) => a.seq - b.seq);
}

export function applyEdits(profile, connectionId, { existingOnly = false } = {}) {
  if (!profile?.name || stacks.size === 0) return profile;
  const edits = editsFor(profileKey(connectionId, profile.name));
  let next = profile;
  for (const { path, value } of edits) {
    if (existingOnly && !(path.split(".")[0] in profile)) continue;
    next = setPath(next, path, value);
  }
  return next;
}

export function applyEditsToRows(rows, connectionId) {
  if (!Array.isArray(rows) || stacks.size === 0) return rows;
  let touched = false;
  const next = rows.map((row) => {
    const patched = applyEdits(row, connectionId, { existingOnly: true });
    if (patched !== row) touched = true;
    return patched;
  });
  return touched ? next : rows;
}

export function subscribeProfileEdits(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function profileEditsVersion() {
  return version;
}

function laneKeys(ticket) {
  return Array.from(new Set(ticket.paths.map((path) => `${ticket.key}\u0000${path.split(".")[0]}`)));
}

function start(run) {
  try {
    return Promise.resolve(run());
  } catch (e) {
    return Promise.reject(e);
  }
}

export function saveOptimistic({ connectionId, name, patch, run, onFailed, refresh }) {
  const ticket = beginEdit(connectionId, name, patch);
  const keys = laneKeys(ticket);
  const ahead = keys.map((k) => lanes.get(k)).filter(Boolean);
  let skipped = false;
  if (ahead.length) queued.add(ticket);
  const request = ahead.length
    ? Promise.all(ahead).then(() => {
      queued.delete(ticket);
      if (ticket.replaced.size < ticket.paths.length) return run();
      skipped = true;
      dropTicket(ticket);
      return undefined;
    })
    : start(run);
  const settled = request.then(() => {}, () => {});
  for (const k of keys) lanes.set(k, settled);
  settled.then(() => {
    for (const k of keys) if (lanes.get(k) === settled) lanes.delete(k);
  });
  return request.then(
    () => ({ ticket, latest: skipped ? false : confirmEdit(ticket) }),
    (error) => {
      const latest = failEdit(ticket);
      if (latest || hasConfirmedSurvivor(ticket)) {
        start(() => refresh?.()).catch(() => {});
      }
      onFailed?.(error, latest);
      throw error;
    },
  );
}

export function _resetProfileEdits() {
  stacks.clear();
  lanes.clear();
  queued.clear();
  clock = 0;
  changed();
}
