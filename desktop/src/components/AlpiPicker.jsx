import { useMemo, useState } from "react";
import Chip from "../primitives/Chip.jsx";
import Dropdown from "../primitives/Dropdown.jsx";
import { Dot } from "../primitives/NavRow.jsx";
import { profileLabel } from "../lib/profile-display.js";

const SEARCH_THRESHOLD = 8;

export default function AlpiPicker({ profiles, activeAlpi, onChange }) {
  const [query, setQuery] = useState("");

  const active = profiles.find((p) => p.name === activeAlpi) ?? null;

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return profiles;
    return profiles.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        profileLabel(p.name).toLowerCase().includes(q) ||
        (p.model ?? "").toLowerCase().includes(q),
    );
  }, [profiles, query]);

  return (
    <Dropdown
      direction="up"
      align="right"
      width={320}
      trigger={{
        label: active ? profileLabel(active.name) : "—",
        title: active?.model ?? "",
        leading: active ? <Dot color={active.accent} /> : null,
      }}
      searchable={profiles.length > SEARCH_THRESHOLD}
      searchPlaceholder="Find alpi…"
      query={query}
      onQueryChange={setQuery}
    >
      {({ close }) => (
        <>
          {filtered.length === 0 && <Dropdown.Empty>No alpis match</Dropdown.Empty>}
          {filtered.map((p) => (
            <Dropdown.Row
              key={p.name}
              active={p.name === activeAlpi}
              caption={p.model ?? null}
              leading={<Dot color={p.accent} />}
              trailing={
                !p.model ? (
                  <Chip size="sm" state="off">
                    no model
                  </Chip>
                ) : null
              }
              onClick={() => {
                onChange(p.name);
                close();
              }}
            >
              {profileLabel(p.name)}
            </Dropdown.Row>
          ))}
        </>
      )}
    </Dropdown>
  );
}

