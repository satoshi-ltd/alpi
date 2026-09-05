import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Chip from "../../../primitives/Chip.jsx";
import Dropdown from "../../../primitives/Dropdown.jsx";
import styles from "../Settings.module.css";

export function WorkgroupsField({
  profile,
  profiles,
  connectionId = null,
  prefetched,
  onSelectWorkgroup,
  onLoadingChange = null,
  onCountChange = null,
  defer = false,
}) {
  const prefetchedMode = prefetched !== undefined;
  const [groups, setGroups] = useState(prefetchedMode ? prefetched : []);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (prefetchedMode) {
      setGroups(prefetched);
      onLoadingChange?.(false);
      return undefined;
    }
    let cancelled = false;
    setGroups([]);
    setLoading(true);
    onLoadingChange?.(true);
    if (defer) return undefined;
    invoke("workgroups", {
      profile: profile.name,
      ...(connectionId ? { connectionId } : {}),
    })
      .then((rows) => { if (!cancelled) setGroups(Array.isArray(rows) ? rows : []); })
      .catch(() => { if (!cancelled) setGroups([]); })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          onLoadingChange?.(false);
        }
      });
    return () => {
      cancelled = true;
      onLoadingChange?.(false);
    };
  }, [profile.name, connectionId, prefetchedMode, prefetched, defer, onLoadingChange]);

  useEffect(() => { onCountChange?.(groups.length); }, [groups.length, onCountChange]);

  if (groups.length === 0) {
    return loading ? <span className={styles.muted}>loading…</span> : null;
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
