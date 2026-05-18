import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Chip,
  Diamond,
  DialogFooter,
  Dropdown,
  Eyebrow,
  Modal,
  Textarea,
} from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { profileLabel } from "../lib/profile-display.js";
import styles from "./CreateWorkgroupModal.module.css";

export default function CreateWorkgroupModal({
  open,
  profiles = [],
  onCreated,
  onClose,
}) {
  const eligibleHubs = useMemo(
    () => profiles.filter((p) => (p.peers ?? []).length > 0),
    [profiles],
  );

  const [hubProfile, setHubProfile] = useState(eligibleHubs[0]?.name ?? "");
  const [name, setName] = useState("");
  const [memberIds, setMemberIds] = useState([]);
  const [briefing, setBriefing] = useState("");
  const [busy, setBusy] = useState(false);
  const notify = useNotify();

  useEffect(() => {
    if (!open) return;
    setHubProfile(eligibleHubs[0]?.name ?? "");
    setName("");
    setMemberIds([]);
    setBriefing("");
    setBusy(false);
  }, [open, eligibleHubs]);

  useEffect(() => {
    setMemberIds([]);
  }, [hubProfile]);

  const hub = profiles.find((p) => p.name === hubProfile);
  const peers = hub?.peers ?? [];

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
          <input
            className={styles.input}
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
                      <div>{(p.pubkey || "").slice(0, 16)}…</div>
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
            className={styles.textarea}
            rows={3}
            value={briefing}
            onChange={(e) => setBriefing(e.target.value)}
            placeholder="what is this workgroup about?"
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
