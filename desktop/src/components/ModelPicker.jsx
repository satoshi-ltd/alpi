import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Chip from "../primitives/Chip.jsx";
import Dropdown from "../primitives/Dropdown.jsx";

const SEARCH_THRESHOLD = 8;

export default function ModelPicker({ profile, models, defaultModel, value, onChange }) {
  const [query, setQuery] = useState("");
  const [ollamaModels, setOllamaModels] = useState([]);
  const [ollamaLoaded, setOllamaLoaded] = useState(false);

  useEffect(() => {
    setOllamaModels([]);
    setOllamaLoaded(false);
  }, [profile]);

  useEffect(() => {
    if (!profile || ollamaLoaded) return;
    let cancelled = false;
    invoke("ollama_models", { profile })
      .then((rows) => {
        if (cancelled) return;
        setOllamaModels(Array.isArray(rows) ? rows : []);
        setOllamaLoaded(true);
      })
      .catch(() => {
        if (!cancelled) setOllamaLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [profile, ollamaLoaded]);

  const list = useMemo(() => {
    const seenId = new Set();
    const seenLabel = new Set();
    const out = [];
    for (const m of [...(models ?? []), ...ollamaModels]) {
      if (!m || seenId.has(m)) continue;
      const label = shortLabel(m);
      if (seenLabel.has(label)) continue;
      seenId.add(m);
      seenLabel.add(label);
      out.push(m);
    }
    return out;
  }, [models, ollamaModels]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return list;
    return list.filter((m) => m.toLowerCase().includes(q));
  }, [list, query]);

  const grouped = useMemo(() => {
    const groups = new Map();
    for (const m of filtered) {
      const provider = m.split("/")[0] || "other";
      if (!groups.has(provider)) groups.set(provider, []);
      groups.get(provider).push(m);
    }
    return [...groups.entries()];
  }, [filtered]);

  const active = value ?? defaultModel ?? null;
  if (list.length <= 1) return null;

  return (
    <Dropdown
      direction="up"
      align="right"
      width={280}
      trigger={{ label: active ? shortLabel(active) : "model", title: active ?? "" }}
      searchable={list.length > SEARCH_THRESHOLD}
      searchPlaceholder="Find model…"
      query={query}
      onQueryChange={setQuery}
    >
      {({ close }) => (
        <>
          {filtered.length === 0 && <Dropdown.Empty>No models match</Dropdown.Empty>}
          {grouped.map(([provider, items]) => (
            <Dropdown.Group key={provider} label={provider}>
              {items.map((m) => (
                <Dropdown.Row
                  key={m}
                  active={m === active}
                  title={m}
                  trailing={
                    m === defaultModel ? (
                      <Chip size="sm" state="on">
                        default
                      </Chip>
                    ) : null
                  }
                  onClick={() => {
                    onChange(m === defaultModel ? null : m);
                    close();
                  }}
                >
                  {shortLabel(m)}
                </Dropdown.Row>
              ))}
            </Dropdown.Group>
          ))}
        </>
      )}
    </Dropdown>
  );
}

function shortLabel(model) {
  const slash = model.lastIndexOf("/");
  return slash === -1 ? model : model.slice(slash + 1);
}
