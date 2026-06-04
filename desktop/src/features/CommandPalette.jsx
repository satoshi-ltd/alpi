import { useMemo } from "react";
import { Palette } from "../primitives/Panels.jsx";
import { I } from "../primitives/icons.jsx";

const GLYPH_BY_PREFIX = {
  "view:settings": () => <I.Gear />,
  "view:find": () => <I.Search />,
  "browse:tools": () => <I.Wrench />,
  "browse:skills": () => <I.Blocks />,
  "browse:memory": () => <I.Cpu />,
  "create:chat": () => <I.Plus />,
  "create:profile": () => <I.Plus />,
  "create:workgroup": () => <I.Plus />,
};

function resolveGlyph(cmd, profiles, workgroups) {
  // nav:profile:<name>  → diamond in profile accent
  if (cmd.id.startsWith("nav:profile:")) {
    const name = cmd.id.slice("nav:profile:".length);
    const p = profiles.find((x) => x.name === name);
    return (
      <span
        className="diamond"
        style={{ "--c": p?.accent || "var(--ink-3)", width: 9, height: 9 }}
      />
    );
  }
  if (cmd.id.startsWith("nav:workgroup:")) {
    return (
      <span
        className="hash"
        style={{
          fontFamily: "var(--font-mono)",
          color: "var(--ink-3)",
          fontSize: "var(--fs-base)",
          fontWeight: 500,
        }}
      >
        #
      </span>
    );
  }
  const make = GLYPH_BY_PREFIX[cmd.id];
  return make ? make() : <I.ChevRight />;
}

export default function CommandPalette({
  open,
  onClose,
  commands,
  profiles = [],
  workgroups = [],
}) {
  const groups = useMemo(() => {
    const byGroup = new Map();
    commands.forEach((c) => {
      if (!byGroup.has(c.group)) byGroup.set(c.group, []);
      byGroup.get(c.group).push({
        id: c.id,
        label: c.label,
        shortcut: c.hint,
        glyph: resolveGlyph(c, profiles, workgroups),
        onSelect: c.action,
      });
    });
    return Array.from(byGroup.entries()).map(([label, items]) => ({
      label,
      items,
    }));
  }, [commands, profiles, workgroups]);

  return <Palette open={open} onClose={onClose} groups={groups} />;
}
