import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Chip from "../primitives/Chip.jsx";
import Dropdown from "../primitives/Dropdown.jsx";

const DAY_MS = 86400000;
const SEARCH_THRESHOLD = 8;

function startOfDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function bucket(ms) {
  const today = startOfDay(new Date());
  if (ms >= today) return "Today";
  if (ms >= today - DAY_MS) return "Yesterday";
  if (ms >= today - 7 * DAY_MS) return "This week";
  return "Earlier";
}

export default function SessionsDropdown({ profile, activeSessionId, onChange }) {
  const [sessions, setSessions] = useState([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    invoke("sessions", { profile }).then((all) => {
      setSessions(all.filter((s) => s.kind === "chat"));
    });
  }, [open, profile]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return sessions;
    return sessions.filter(
      (s) =>
        s.first_user.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q),
    );
  }, [sessions, query]);

  const grouped = useMemo(() => {
    const out = {};
    for (const s of filtered) {
      const b = bucket(s.mtime * 1000);
      (out[b] ||= []).push(s);
    }
    return out;
  }, [filtered]);

  return (
    <Dropdown
      direction="down"
      align="right"
      width={360}
      trigger={{ label: "Sessions", title: "Switch session" }}
      searchable={sessions.length > SEARCH_THRESHOLD}
      searchPlaceholder="Find session…"
      query={query}
      onQueryChange={setQuery}
      onOpenChange={setOpen}
    >
      {({ close }) => (
        <>
          {filtered.length === 0 && <Dropdown.Empty>No sessions</Dropdown.Empty>}
          {Object.entries(grouped).map(([label, list]) => (
            <Dropdown.Group key={label} label={label}>
              {list.map((s) => (
                <Dropdown.Row
                  key={s.id}
                  active={s.id === activeSessionId}
                  trailing={
                    <Chip size="sm">
                      {s.turn_count} {s.turn_count === 1 ? "turn" : "turns"}
                    </Chip>
                  }
                  onClick={() => {
                    onChange(s.id);
                    close();
                  }}
                >
                  {s.first_user || `(empty · ${s.id.slice(0, 6)})`}
                </Dropdown.Row>
              ))}
            </Dropdown.Group>
          ))}
        </>
      )}
    </Dropdown>
  );
}
