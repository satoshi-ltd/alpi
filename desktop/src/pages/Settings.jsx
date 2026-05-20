import { useEffect, useMemo } from "react";
import ProfileDetail from "../features/settings/ProfileDetail.jsx";
import WorkgroupDetail from "../features/settings/WorkgroupDetail.jsx";
import styles from "../features/settings/Settings.module.css";

export default function Settings({
  profiles,
  workgroups = [],
  target,
  activeConnection,
  refreshTick = 0,
  onSelectTarget,
  onRefresh,
  onOpenChat,
}) {
  const setTarget = onSelectTarget ?? (() => {});

  const selectedProfile = useMemo(() => {
    if (target?.kind !== "profile") return null;
    return profiles.find((p) => p.name === target.id) ?? null;
  }, [profiles, target]);

  const selectedWorkgroup = useMemo(() => {
    if (target?.kind !== "workgroup") return null;
    return workgroups.find((w) => w.id === target.id) ?? null;
  }, [workgroups, target]);

  // Default the first time settings opens with no target.
  useEffect(() => {
    if (!target || (target.kind === "profile" && !target.id)) {
      const first = profiles[0]?.name ?? null;
      if (first) setTarget({ kind: "profile", id: first });
    }
  }, [profiles, target, setTarget]);

  return (
    <div className={styles.wrap}>
      {selectedProfile && (
        <ProfileDetail
          key={`${selectedProfile.name}:${refreshTick}`}
          profile={selectedProfile}
          profiles={profiles}
          activeConnection={activeConnection}
          onSaved={onRefresh}
          onNavigate={setTarget}
          onOpenChat={onOpenChat}
        />
      )}
      {selectedWorkgroup && (
        <WorkgroupDetail
          key={`${selectedWorkgroup.id}:${refreshTick}`}
          workgroup={selectedWorkgroup}
          profiles={profiles}
          connectionId={activeConnection?.id ?? null}
          onSaved={onRefresh}
          onOpenChat={onOpenChat}
        />
      )}
      {!selectedProfile && !selectedWorkgroup && (
        <div className={styles.empty}>No selection</div>
      )}
    </div>
  );
}
