import { useEffect, useMemo, useRef } from "react";
import ConnectionSwitcher from "./ConnectionSwitcher.jsx";
import NavRow, { Dot, Hash } from "../primitives/NavRow.jsx";
import Kbd from "../primitives/Kbd.jsx";
import VersionFooter from "./settings/VersionFooter.jsx";
import ProfileDetail from "./settings/ProfileDetail.jsx";
import WorkgroupDetail from "./settings/WorkgroupDetail.jsx";
import CreateProfileForm from "./settings/CreateProfileForm.jsx";
import CreateWorkgroupForm from "./settings/CreateWorkgroupForm.jsx";
import { PinIcon, PinOffIcon } from "../primitives/icons.jsx";
import { profileLabel } from "../lib/profile-display.js";
import { orderedSidebarProfiles } from "../lib/profile-order.js";
import styles from "./Settings.module.css";

export default function Settings({
  profiles,
  workgroups = [],
  target,
  hostConnections,
  activeConnection,
  refreshTick = 0,
  pinned = { profiles: [], workgroups: [] },
  jumpHints = {},
  onTogglePin,
  onSelectTarget,
  onRefresh,
  onSetHostConnection,
  onAddHostConnection,
  onForgetHostConnection,
  onRefreshHostConnectionStatus,
}) {
  const setTarget = onSelectTarget ?? (() => {});
  const pinnedProfileNames = pinned?.profiles ?? [];
  const pinnedWorkgroupKeys = pinned?.workgroups ?? [];

  const pinnedProfiles = useMemo(
    () =>
      pinnedProfileNames
        .map((name) => profiles.find((p) => p.name === name))
        .filter(Boolean),
    [pinnedProfileNames, profiles],
  );

  const pinnedWorkgroups = useMemo(
    () =>
      pinnedWorkgroupKeys
        .map((k) => workgroups.find((w) => `${w.profile}/${w.id}` === k))
        .filter(Boolean),
    [pinnedWorkgroupKeys, workgroups],
  );

  const unpinnedProfiles = useMemo(() => {
    const pinnedSet = new Set(pinnedProfileNames);
    return orderedSidebarProfiles(profiles, pinnedProfileNames).filter(
      (p) => !pinnedSet.has(p.name),
    );
  }, [profiles, pinnedProfileNames]);

  const unpinnedWorkgroups = useMemo(() => {
    const pinnedSet = new Set(pinnedWorkgroupKeys);
    return workgroups.filter(
      (w) => !pinnedSet.has(`${w.profile}/${w.id}`),
    );
  }, [workgroups, pinnedWorkgroupKeys]);

  const hasPinned = pinnedProfiles.length > 0 || pinnedWorkgroups.length > 0;

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

  const asideRef = useRef(null);
  useEffect(() => {
    const active = asideRef.current?.querySelector("[data-active='true']");
    active?.scrollIntoView({ block: "nearest" });
  }, [target?.kind, target?.id]);

  return (
    <div className={styles.wrap}>
      <aside ref={asideRef} className={styles.aside}>
        <div className={styles.asideTop}>
          <ConnectionSwitcher
            className={styles.connectionSwitcher}
            state={hostConnections}
            onSetActive={onSetHostConnection}
            onAddRemote={onAddHostConnection}
            onForget={onForgetHostConnection}
            onOpen={onRefreshHostConnectionStatus}
          />
        </div>

        <div className={styles.asideScroll}>
        {hasPinned && (
          <>
            <div className={styles.asideTitle}>Pinned</div>
            {pinnedProfiles.map((p) =>
              renderProfileRow(p, {
                target,
                setTarget,
                pinnedProfileNames,
                jumpHints,
                onTogglePin,
                keyPrefix: "pin:",
              }),
            )}
            {pinnedWorkgroups.map((w) =>
              renderWorkgroupRow(w, {
                target,
                setTarget,
                profiles,
                pinnedWorkgroupKeys,
                jumpHints,
                onTogglePin,
                keyPrefix: "pin:",
              }),
            )}
          </>
        )}

        <div
          className={styles.asideTitle}
          style={hasPinned ? { marginTop: "var(--space-3)" } : undefined}
        >
          Profiles
        </div>
        {unpinnedProfiles.map((p) =>
          renderProfileRow(p, {
            target,
            setTarget,
            pinnedProfileNames,
            jumpHints,
            onTogglePin,
          }),
        )}
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
        {unpinnedWorkgroups.map((w) =>
          renderWorkgroupRow(w, {
            target,
            setTarget,
            profiles,
            pinnedWorkgroupKeys,
            jumpHints,
            onTogglePin,
          }),
        )}
        <NavRow
          active={target?.kind === "create-workgroup"}
          leading={<Hash>+</Hash>}
          onClick={() => setTarget({ kind: "create-workgroup" })}
        >
          New workgroup
        </NavRow>
        </div>
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

function renderProfileRow(
  p,
  { target, setTarget, pinnedProfileNames, jumpHints, onTogglePin, keyPrefix = "" },
) {
  const active = target?.kind === "profile" && target.id === p.name;
  const isPinned = pinnedProfileNames.includes(p.name);
  const hint = jumpHints?.[`profile:${p.name}`];
  return (
    <div
      key={`${keyPrefix}${p.name}`}
      className={styles.rowWrap}
      data-active={active ? "true" : undefined}
    >
      <NavRow
        active={active}
        accent={p.accent || "var(--color-accent)"}
        muted={!p.model}
        leading={<Dot color={p.accent} />}
        trailing={
          <span className={styles.trailingCluster}>
            {!p.model && (
              <span className={styles.asideTag} title="No model configured">
                !
              </span>
            )}
            {hint && <JumpHint n={hint} />}
            <PinToggle
              isPinned={isPinned}
              onToggle={() => onTogglePin?.("profiles", p.name)}
            />
          </span>
        }
        onClick={() => setTarget({ kind: "profile", id: p.name })}
      >
        {profileLabel(p.name)}
      </NavRow>
    </div>
  );
}

function renderWorkgroupRow(
  w,
  {
    target,
    setTarget,
    profiles,
    pinnedWorkgroupKeys,
    jumpHints,
    onTogglePin,
    keyPrefix = "",
  },
) {
  const active = target?.kind === "workgroup" && target.id === w.id;
  const hub = profiles.find((p) => p.name === (w.hub_id ?? w.profile));
  const accent = hub?.accent || "var(--color-accent)";
  const key = `${w.profile}/${w.id}`;
  const isPinned = pinnedWorkgroupKeys.includes(key);
  const hint = jumpHints?.[`workgroup:${key}`];
  return (
    <div
      key={`${keyPrefix}${w.id}`}
      className={styles.rowWrap}
      data-active={active ? "true" : undefined}
    >
      <NavRow
        active={active}
        accent={accent}
        leading={<Hash />}
        trailing={
          <span className={styles.trailingCluster}>
            {hint && <JumpHint n={hint} />}
            <PinToggle
              isPinned={isPinned}
              onToggle={() => onTogglePin?.("workgroups", key)}
            />
          </span>
        }
        onClick={() => setTarget({ kind: "workgroup", id: w.id })}
      >
        {w.name || w.id}
      </NavRow>
    </div>
  );
}

function JumpHint({ n }) {
  return (
    <span className={styles.jumpHintWrap} aria-hidden>
      <Kbd>⌘{n}</Kbd>
    </span>
  );
}

function PinToggle({ isPinned, onToggle }) {
  return (
    <button
      type="button"
      className={styles.pinToggle}
      onClick={(e) => {
        e.stopPropagation();
        onToggle?.();
      }}
      title={isPinned ? "Unpin" : "Pin"}
      aria-label={isPinned ? "Unpin" : "Pin"}
    >
      {isPinned ? <PinOffIcon size={12} /> : <PinIcon size={12} />}
    </button>
  );
}
