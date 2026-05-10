import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../primitives/Button.jsx";
import Chip from "../../primitives/Chip.jsx";
import Dropdown from "../../primitives/Dropdown.jsx";
import Textarea from "../../primitives/Textarea.jsx";
import { AccentDot } from "../../primitives/NavRow.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import { profileLabel } from "../../lib/profile-display.js";
import { Section, Row } from "./primitives.jsx";
import styles from "../Settings.module.css";

export default function CreateWorkgroupForm({ profiles, onCreated, onCancel }) {
  const [hubProfile, setHubProfile] = useState(profiles[0]?.name ?? "");
  const [name, setName] = useState("");
  const [memberIds, setMemberIds] = useState([]);
  const [budget, setBudget] = useState("");
  const [briefing, setBriefing] = useState("");
  const [busy, setBusy] = useState(false);
  const notify = useNotify();

  const peers = useMemo(
    () => profiles.find((x) => x.name === hubProfile)?.peers ?? [],
    [profiles, hubProfile],
  );

  useEffect(() => {
    setMemberIds([]);
  }, [hubProfile]);

  const budgetNum = budget.trim() === "" ? null : Number(budget);
  const budgetValid =
    budget.trim() === "" ||
    (Number.isFinite(budgetNum) && budgetNum > 0);
  const canSubmit =
    !busy && hubProfile && name.trim().length > 0 && budgetValid;

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
        budgetUsd: budgetNum,
        briefing: briefing.trim() || null,
      });
      notify({ message: `Workgroup #${name.trim()} created`, variant: "success" });
      onCreated?.(wgId);
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

  return (
    <main className={styles.detail}>
      <div className={styles.body}>
        <Section title="New workgroup">
          <Row label="hub">
            <Dropdown
              trigger={{
                leading: hubProfile && (
                  <AccentDot
                    color={profiles.find((p) => p.name === hubProfile)?.accent}
                  />
                ),
                label: hubProfile ? profileLabel(hubProfile) : "Pick profile…",
              }}
              direction="down"
              align="left"
              width={260}
              variant="outlined"
            >
              {({ close }) =>
                profiles.map((p) => (
                  <Dropdown.Row
                    key={p.name}
                    active={p.name === hubProfile}
                    leading={<AccentDot color={p.accent} />}
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
          </Row>
          <Row label="name">
            <input
              className={styles.input}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="team-alpha"
              spellCheck={false}
            />
          </Row>
          <Row label="members" alignTop>
            {peers.length === 0 ? (
              <span className={styles.muted}>
                @{profileLabel(hubProfile)} has no pinned peers
              </span>
            ) : (
              <span className={styles.gatewayChips}>
                {peers.map((p) => {
                  const local = profiles.find((x) => x.name === p.id);
                  const accent = local?.accent || "var(--color-accent)";
                  const selected = memberIds.includes(p.id);
                  return (
                    <Chip
                      key={p.id}
                      onClick={() => toggleMember(p.id)}
                      accent={selected ? accent : undefined}
                      tooltip={
                        <>
                          <div>@{p.id}</div>
                          <div className={styles.tooltipStatus}>
                            {(p.pubkey || "").slice(0, 16)}…
                          </div>
                        </>
                      }
                    >
                      @{p.id}
                    </Chip>
                  );
                })}
              </span>
            )}
          </Row>
          <Row label="budget">
            <span className={styles.inlineRow}>
              <input
                className={styles.input}
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="USD lifetime cap (optional)"
                spellCheck={false}
                style={{ maxWidth: 220 }}
              />
              {!budgetValid && (
                <span className={styles.error}>must be a positive number</span>
              )}
            </span>
          </Row>
          <Row label="briefing" alignTop>
            <Textarea
              className={styles.textarea}
              rows={3}
              value={briefing}
              onChange={(e) => setBriefing(e.target.value)}
              placeholder="what is this workgroup about? who does what?"
            />
          </Row>
          <Row label=" ">
            <span className={styles.inlineRow}>
              <Button onClick={onCancel} disabled={busy}>Cancel</Button>
              <Button
                variant="primary"
                onClick={submit}
                disabled={!canSubmit}
                loading={busy}
              >
                Create
              </Button>
            </span>
          </Row>
        </Section>
      </div>
    </main>
  );
}
