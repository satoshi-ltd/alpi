import { useMemo } from "react";
import { Palette } from "../primitives/Panels.jsx";
import { I } from "../primitives/icons.jsx";

const GLYPH_BY_PREFIX = {
  "view:settings": () => <I.Gear />,
  "view:find": () => <I.Search />,
  "view:notifications": () => <I.Bell />,
  "chat:find": () => <I.Search />,
  "chat:refresh": () => <I.Refresh />,
  "chat:read-aloud": () => <I.Volume />,
  "profile:sessions": () => <I.Archive />,
  "profile:pause": () => <I.Pause />,
  "workgroup:tasks": () => <I.Check />,
  "workgroup:pause": () => <I.Pause />,
  "workgroup:refresh": () => <I.Refresh />,
  "profile:tools": () => <I.Wrench />,
  "profile:skills": () => <I.Blocks />,
  "profile:memory": () => <I.Cpu />,
  "create:chat": () => <I.Plus />,
  "create:profile": () => <I.Plus />,
  "create:workgroup": () => <I.Plus />,
};

function resolveGlyph(cmd) {
  const make = GLYPH_BY_PREFIX[cmd.id];
  return make ? make() : <I.ChevRight />;
}

export default function CommandPalette({ open, onClose, commands }) {
  const groups = useMemo(() => {
    const byGroup = new Map();
    commands.forEach((c) => {
      if (!byGroup.has(c.group)) byGroup.set(c.group, []);
      byGroup.get(c.group).push({
        id: c.id,
        label: c.label,
        shortcut: c.hint,
        glyph: resolveGlyph(c),
        onSelect: c.action,
      });
    });
    return Array.from(byGroup.entries()).map(([label, items]) => ({
      label,
      items,
    }));
  }, [commands]);

  return <Palette open={open} onClose={onClose} groups={groups} />;
}
