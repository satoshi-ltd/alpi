import { useMemo, useState } from "react";
import Chip from "../primitives/Chip.jsx";
import Dropdown from "../primitives/Dropdown.jsx";
import { AlpiIcon } from "../primitives/icons.jsx";

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
        (p.model ?? "").toLowerCase().includes(q),
    );
  }, [profiles, query]);

  return (
    <Dropdown
      direction="up"
      align="right"
      width={320}
      trigger={{
        label: active?.name ?? "—",
        title: active?.model ?? "",
        leading: active ? <Dot accent={active.accent} /> : null,
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
              leading={<Dot accent={p.accent} />}
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
              {p.name}
            </Dropdown.Row>
          ))}
        </>
      )}
    </Dropdown>
  );
}

function Dot({ accent }) {
  return (
    <AlpiIcon color={accent || "var(--color-accent)"} />
  );
}
