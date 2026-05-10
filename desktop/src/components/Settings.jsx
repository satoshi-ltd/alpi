import { useEffect, useMemo } from "react";
import ConnectionSwitcher from "./ConnectionSwitcher.jsx";
import NavRow, { Dot, Hash } from "../primitives/NavRow.jsx";
import VersionFooter from "./settings/VersionFooter.jsx";
import ProfileDetail from "./settings/ProfileDetail.jsx";
import WorkgroupDetail from "./settings/WorkgroupDetail.jsx";
import CreateProfileForm from "./settings/CreateProfileForm.jsx";
import CreateWorkgroupForm from "./settings/CreateWorkgroupForm.jsx";
import { profileLabel } from "../lib/profile-display.js";
import styles from "./Settings.module.css";

export default function Settings({
  profiles,
  workgroups = [],
  target,
  hostConnections,
  activeConnection,
  refreshTick = 0,
  onSelectTarget,
  onRefresh,
  onSetHostConnection,
  onAddHostConnection,
  onForgetHostConnection,
  onRefreshHostConnectionStatus,
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

  useEffect(() => {
    if (!target || (target.kind === "profile" && !target.id)) {
      const first = profiles[0]?.name ?? null;
      if (first) setTarget({ kind: "profile", id: first });
    }
  }, [profiles, target, setTarget]);

  return (
    <div className={styles.wrap}>
      <aside className={styles.aside}>
        <div className={styles.asideTitle}>Connection</div>
        <ConnectionSwitcher
          className={styles.connectionSwitcher}
          state={hostConnections}
          onSetActive={onSetHostConnection}
          onAddRemote={onAddHostConnection}
          onForget={onForgetHostConnection}
          onOpen={onRefreshHostConnectionStatus}
        />

        <div className={styles.asideTitle}>Profiles</div>
        {profiles.map((p) => {
          const active = target?.kind === "profile" && target.id === p.name;
          return (
            <NavRow
              key={p.name}
              active={active}
              accent={p.accent || "var(--color-accent)"}
              muted={!p.model}
              leading={<Dot color={p.accent} />}
              trailing={
                !p.model && (
                  <span
                    className={styles.asideTag}
                    title="No model configured"
                  >
                    !
                  </span>
                )
              }
              onClick={() => setTarget({ kind: "profile", id: p.name })}
            >
              {profileLabel(p.name)}
            </NavRow>
          );
        })}
        <NavRow
          active={target?.kind === "create-profile"}
          leading={<Hash>+</Hash>}
          onClick={() => setTarget({ kind: "create-profile" })}
        >
          New profile
        </NavRow>

        <div className={styles.asideTitle} style={{ marginTop: "var(--space-3)" }}>
          Workgroups
        </div>
        {workgroups.map((w) => {
          const active = target?.kind === "workgroup" && target.id === w.id;
          const hub = profiles.find(
            (p) => p.name === (w.hub_id ?? w.profile),
          );
          const accent = hub?.accent || "var(--color-accent)";
          return (
            <NavRow
              key={w.id}
              active={active}
              accent={accent}
              leading={<Hash />}
              onClick={() => setTarget({ kind: "workgroup", id: w.id })}
            >
              {w.name || w.id}
            </NavRow>
          );
        })}
        <NavRow
          active={target?.kind === "create-workgroup"}
          leading={<Hash>+</Hash>}
          onClick={() => setTarget({ kind: "create-workgroup" })}
        >
          New workgroup
        </NavRow>
        <VersionFooter />
      </aside>

      {selectedProfile && (
        <ProfileDetail
          key={`${selectedProfile.name}:${refreshTick}`}
          profile={selectedProfile}
          profiles={profiles}
          activeConnection={activeConnection}
          onSaved={onRefresh}
          onNavigate={setTarget}
        />
      )}
      {selectedWorkgroup && (
        <WorkgroupDetail
          key={`${selectedWorkgroup.id}:${refreshTick}`}
          workgroup={selectedWorkgroup}
          profiles={profiles}
          onSaved={onRefresh}
        />
      )}
      {target?.kind === "create-profile" && (
        <CreateProfileForm
          existingNames={profiles.map((p) => p.name)}
          onCreated={async (name) => {
            await onRefresh?.();
            setTarget({ kind: "profile", id: name });
          }}
          onCancel={() => {
            const first = profiles[0]?.name ?? null;
            if (first) setTarget({ kind: "profile", id: first });
          }}
        />
      )}
      {target?.kind === "create-workgroup" && (
        <CreateWorkgroupForm
          profiles={profiles}
          onCreated={async (wgId) => {
            await onRefresh?.();
            if (wgId) setTarget({ kind: "workgroup", id: wgId });
          }}
          onCancel={() => {
            const first = profiles[0]?.name ?? null;
            if (first) setTarget({ kind: "profile", id: first });
          }}
        />
      )}
      {!selectedProfile &&
        !selectedWorkgroup &&
        target?.kind !== "create-workgroup" &&
        target?.kind !== "create-profile" && (
          <div className={styles.empty}>No selection</div>
        )}
    </div>
  );
}
