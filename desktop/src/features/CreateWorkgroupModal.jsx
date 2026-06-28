import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Chip,
  Diamond,
  DialogFooter,
  Dropdown,
  Eyebrow,
  Field,
  Modal,
  Textarea,
} from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { useProfileDetail } from "../hooks/useProfileDetail.js";
import { profileLabel } from "../lib/profile-display.js";
import styles from "./CreateWorkgroupModal.module.css";
import { shortPubkey } from "../lib/pubkey.js";

export default function CreateWorkgroupModal({
  open,
  profiles = [],
  connectionId = null,
  onCreated,
  onClose,
}) {
  // Hub eligibility (has peers) comes from the lightweight `counts.peers` on the summary — peering through the full peer array per profile would force a detail fetch for every profile, which is exactly what we just split apart.
  const eligibleHubs = useMemo(
    () => profiles.filter((p) => (p.counts?.peers ?? p.peers?.length ?? 0) > 0),
    [profiles],
  );

  const [hubProfile, setHubProfile] = useState(eligibleHubs[0]?.name ?? "");
  const [name, setName] = useState("");
  const [memberIds, setMemberIds] = useState([]);
  const [briefing, setBriefing] = useState("");
  const [pipeline, setPipeline] = useState("");
  const [busy, setBusy] = useState(false);
  const notify = useNotify();

  useEffect(() => {
    if (!open) return;
    setHubProfile(eligibleHubs[0]?.name ?? "");
    setName("");
    setMemberIds([]);
    setBriefing("");
    setPipeline("");
    setBusy(false);
  }, [open, eligibleHubs]);

  useEffect(() => {
    setMemberIds([]);
  }, [hubProfile]);

  const hub = useMemo(
    () => eligibleHubs.find((p) => p.name === hubProfile) ?? null,
    [eligibleHubs, hubProfile],
  );

  // Lazy peer list for the selected hub, scoped by (connection, profile) so two daemons with the same `doc` profile never bleed peers across.
  const { detail: hubDetail } = useProfileDetail(connectionId, hubProfile || null);
  const peers = hubDetail?.peers ?? [];

  const canSubmit =
    !busy && hubProfile && name.trim().length > 0 && memberIds.length > 0;

  function toggleMember(peerId) {
    setMemberIds((prev) =>
      prev.includes(peerId)
        ? prev.filter((id) => id !== peerId)
        : [...prev, peerId],
    );
  }

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    try {
      const wgId = await invoke("workgroup_create", {
        profile: hubProfile,
        name: name.trim(),
        memberPeerIds: memberIds,
        budgetUsd: null,
        briefing: briefing.trim() || null,
        pipeline: pipeline.trim() || null,
        ...(connectionId ? { connectionId } : {}),
      });
      notify({ message: `Workgroup #${name.trim()} created`, variant: "success" });
      onCreated?.(wgId, hubProfile);
    } catch (e) {
      notify({
        message: `create failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;

  if (eligibleHubs.length === 0) {
    return (
      <Modal open title="New workgroup" onClose={onClose} width="var(--modal-md)">
        <div className={styles.emptyState}>
          <div>
            No profile has any ALP peers yet. A workgroup needs at least one
            peer to invite as a member.
          </div>
          <div>
            Open a profile and add a peer from{" "}
            <code>Settings → peers</code>, then come back here.
          </div>
        </div>
        <div className={styles.footer}>
          <DialogFooter onCancel={onClose} cancelLabel="Close" />
        </div>
      </Modal>
    );
  }

  return (
    <Modal open title="New workgroup" onClose={onClose} width="var(--modal-md)">
      <div className={styles.body}>
        <div className={styles.field}>
          <Eyebrow>HUB</Eyebrow>
          <Dropdown
            trigger={{
              leading: hub && <Diamond color={hub.accent} />,
              label: hub ? `@${profileLabel(hub.name)}` : "Pick profile…",
              trailing: hub?.model || undefined,
            }}
            direction="down"
            align="left"
            width="var(--pop-sm)"
            variant="field"
            fullWidth
          >
            {({ close }) =>
              eligibleHubs.map((p) => (
                <Dropdown.Row
                  key={p.name}
                  active={p.name === hubProfile}
                  leading={<Diamond color={p.accent} />}
                  caption={p.model || undefined}
                  onClick={() => {
                    setHubProfile(p.name);
                    close();
                  }}
                >
                  @{profileLabel(p.name)}
                </Dropdown.Row>
              ))
            }
          </Dropdown>
        </div>

        <div className={styles.field}>
          <Eyebrow>NAME</Eyebrow>
          <Field
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && canSubmit) submit();
            }}
            placeholder="team-alpha · roadmap · customers"
            spellCheck={false}
            autoFocus
          />
        </div>

        <div className={styles.field}>
          <Eyebrow>
            MEMBERS — PEERS OF @{profileLabel(hubProfile)}
          </Eyebrow>
          <div className={styles.chips}>
            {peers.map((p) => {
              const local = profiles.find((x) => x.name === p.id);
              const accent = local?.accent || "var(--accent)";
              const selected = memberIds.includes(p.id);
              return (
                <Chip
                  key={p.id}
                  onClick={() => toggleMember(p.id)}
                  accent={selected ? accent : undefined}
                  tooltip={
                    <>
                      <div>@{p.id}</div>
                      <div>{shortPubkey(p.pubkey)}</div>
                    </>
                  }
                >
                  <Diamond color={accent} /> @{p.id}
                </Chip>
              );
            })}
          </div>
        </div>

        <div className={styles.field}>
          <Eyebrow>BRIEFING (OPTIONAL)</Eyebrow>
          <Textarea
            className="ds-field"
            rows={3}
            value={briefing}
            onChange={(e) => setBriefing(e.target.value)}
            placeholder="what is this workgroup about?"
          />
        </div>

        <div className={styles.field}>
          <Eyebrow>PIPELINE (OPTIONAL)</Eyebrow>
          <Field
            value={pipeline}
            onChange={(e) => setPipeline(e.target.value)}
            placeholder="intake, content, build, qa"
          />
        </div>

        <div className={styles.footer}>
          <DialogFooter
            onCancel={onClose}
            primaryLabel="Create"
            primaryDisabled={!canSubmit}
            primaryLoading={busy}
            onPrimary={submit}
          />
        </div>
      </div>
    </Modal>
  );
}
