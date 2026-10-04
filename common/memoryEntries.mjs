export const MEMORY_FILES = [
  { file: "AGENT.md", label: "Identity", caption: (name) => `who ${name} is` },
  { file: "MEMORY.md", label: "Learned", caption: (name) => `what ${name} has learned` },
  { file: "USER.md", label: "About you", caption: (name) => `what ${name} knows about you` },
];

const META = /<!--\s*alpi-meta\s+([^>]*?)\s*-->/gi;

export function memoryFile(file) {
  return MEMORY_FILES.find((f) => f.file === file) ?? { file, label: file, caption: () => "" };
}

function parseMeta(text) {
  const matches = [...String(text).matchAll(META)];
  if (!matches.length) return {};
  return Object.fromEntries([...matches.at(-1)[1].matchAll(/(\w+)=(\S+)/g)].map((m) => [m[1], m[2]]));
}

export function memoryEntries(text) {
  return String(text || "")
    .split(/\n?^§$\n?/m)
    .map((chunk) => {
      const meta = parseMeta(chunk);
      const body = chunk.replace(META, "").trim();
      const reinforced = Number(meta.reinforced);
      return {
        text: body,
        captured: /^\d{4}-\d{2}-\d{2}$/.test(meta.captured ?? "") ? meta.captured : null,
        reinforced: Number.isFinite(reinforced) && reinforced > 0 ? reinforced : 0,
        confidence: meta.conf ?? null,
      };
    })
    .filter((e) => e.text);
}

export function entryNote(entry, formatDate = (d) => d) {
  return [
    entry.captured ? `captured ${formatDate(entry.captured)}` : null,
    entry.reinforced ? `reinforced ×${entry.reinforced}` : null,
    entry.confidence === "low" ? "low confidence" : null,
  ].filter(Boolean).join(" · ");
}
