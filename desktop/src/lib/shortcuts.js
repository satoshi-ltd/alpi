export const SHORTCUTS = [
  { id: "palette", keys: "⌘K", group: "General", label: "Command palette" },
  { id: "shortcuts", keys: "⌘/", group: "General", label: "Keyboard shortcuts" },
  { id: "activity", keys: "⌘J", group: "General", label: "Activity" },
  { id: "jump", keys: "⌘1–9", group: "General", label: "Jump to profile / workgroup" },
  { id: "filter", keys: "⌘S", group: "General", label: "Filter profiles & workgroups" },
  { id: "settings", keys: "⌘,", group: "General", label: "Open or close settings" },
  { id: "notifications", keys: "⌘O", group: "General", label: "Notifications" },
  { id: "new-session", keys: "⌘N", group: "Chat", label: "New session" },
  { id: "send", keys: "⌘↵", group: "Chat", label: "Send message" },
  { id: "find", keys: "⌘F", group: "Chat", label: "Find in transcript" },
  { id: "read-aloud", keys: "⇧⌘L", group: "Chat", label: "Read aloud" },
  { id: "history", keys: "⇧⌘H", group: "Profile or workgroup", label: "Sessions · task history" },
  { id: "refresh", keys: "⇧⌘R", group: "Profile or workgroup", label: "Refresh thread" },
  { id: "pause", keys: "⇧⌘P", group: "Profile or workgroup", label: "Pause or resume" },
  { id: "tools", keys: "⇧⌘T", group: "Profile", label: "Tools" },
  { id: "skills", keys: "⇧⌘S", group: "Profile", label: "Skills" },
  { id: "memory", keys: "⇧⌘M", group: "Profile", label: "Memory" },
  { id: "schedule", keys: "⇧⌘E", group: "Profile", label: "Schedule" },
  { id: "new-profile", keys: "⇧⌘N", group: "Create", label: "New profile" },
  { id: "new-workgroup", keys: "⇧⌘W", group: "Create", label: "New workgroup" },
  { id: "zoom-in", keys: "⌘+", group: "View", label: "Zoom in" },
  { id: "zoom-out", keys: "⌘-", group: "View", label: "Zoom out" },
  { id: "zoom-reset", keys: "⌘0", group: "View", label: "Reset zoom" },
  { id: "close", keys: "Esc", group: "View", label: "Close / dismiss" },
];

const BY_ID = new Map(SHORTCUTS.map((s) => [s.id, s]));

export function shortcutKeys(id) {
  return BY_ID.get(id)?.keys ?? null;
}

const MODIFIERS = new Set(["⌘", "⇧", "⌥", "⌃"]);

export function keyTokens(hint) {
  if (typeof hint !== "string") return null;
  const text = hint.trim();
  const chars = Array.from(text);
  let i = 0;
  while (i < chars.length && MODIFIERS.has(chars[i])) i += 1;
  const rest = chars.slice(i).join("");
  if (!rest || /\s/.test(rest) || Array.from(rest).length > 5) return null;
  return [...chars.slice(0, i), rest];
}
