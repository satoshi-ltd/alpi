import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Chip from "../../../primitives/Chip.jsx";
import Dropdown from "../../../primitives/Dropdown.jsx";
import styles from "../Settings.module.css";

export function WorkgroupsField({ profile, profiles, onSelectWorkgroup }) {
  const [groups, setGroups] = useState([]);
  useEffect(() => {
    invoke("workgroups", { profile: profile.name })
      .then(setGroups)
      .catch(() => setGroups([]));
  }, [profile.name]);

  if (groups.length === 0) {
    return <span className={styles.muted}>none</span>;
  }

  const hubCount = groups.filter((g) => g.is_hub).length;
  const countLabel =
    groups.length === 1 ? "1 workgroup" : `${groups.length} workgroups`;
  const hubLabel =
    hubCount === 0
      ? ""
      : ` · ${hubCount} ${hubCount === 1 ? "hub" : "hubs"}`;

  return (
    <Dropdown
      trigger={{ label: `${countLabel}${hubLabel}` }}
      direction="down"
      align="left"
      width={320}
      variant="field"
    >
      {({ close }) => (
        <>
          {groups.map((g) => {
            const hubAccent =
              profiles?.find((p) => p.name === (g.hub_id ?? profile.name))
                ?.accent || "var(--accent)";
            return (
              <Dropdown.Row
                key={g.id}
                onClick={() => {
                  onSelectWorkgroup?.(g.id);
                  close?.();
                }}
                caption={`${g.members} ${g.members === 1 ? "member" : "members"}`}
                trailing={
                  g.is_hub ? (
                    <Chip size="sm" accent={hubAccent}>hub</Chip>
                  ) : (
                    <Chip size="sm">member</Chip>
                  )
                }
              >
                #{g.name || g.id}
              </Dropdown.Row>
            );
          })}
        </>
      )}
    </Dropdown>
  );
}
