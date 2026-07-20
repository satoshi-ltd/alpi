import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Button,
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
  // counts.peers avoids a per-profile detail fetch just to test hub eligibility.
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
  const [importing, setImporting] = useState(false);
  const [recipeYaml, setRecipeYaml] = useState(null);
  const [recipeMeta, setRecipeMeta] = useState(null);
  const [paramValues, setParamValues] = useState({});
  const [inputValues, setInputValues] = useState({});
  const notify = useNotify();

  useEffect(() => {
    if (!open) return;
    setHubProfile("");
    setName("");
    setMemberIds([]);
    setBriefing("");
    setPipeline("");
    setBusy(false);
    setImporting(false);
    setRecipeYaml(null);
    setRecipeMeta(null);
    setParamValues({});
    setInputValues({});
  }, [open]);

  useEffect(() => {
    if (!open || recipeMeta) return;
    setHubProfile((cur) => cur || eligibleHubs[0]?.name || "");
  }, [open, eligibleHubs, recipeMeta]);

  useEffect(() => {
    setMemberIds([]);
  }, [hubProfile]);

  const hub = useMemo(
    () => eligibleHubs.find((p) => p.name === hubProfile) ?? null,
    [eligibleHubs, hubProfile],
  );

  const { detail: hubDetail } = useProfileDetail(connectionId, hubProfile || null);
  const peers = hubDetail?.peers ?? [];

  const isRecipe = !!recipeMeta;
  const recipeHub = recipeMeta?.hub || "";
  const declaredParams = recipeMeta?.params || {};
  const declaredInputs = recipeMeta?.inputs || {};
  const paramsFilled = Object.keys(declaredParams).every(
    (k) => (paramValues[k] || "").trim().length > 0,
  );
  const inputsFilled = Object.entries(declaredInputs).every(
    ([k, spec]) => !spec.required || (inputValues[k] || "").trim().length > 0,
  );

  const canSubmit = isRecipe
    ? !busy && !importing && !!recipeHub && paramsFilled && inputsFilled
    : !busy && !importing && hubProfile && name.trim().length > 0 && memberIds.length > 0;

  async function pickRecipe() {
    if (importing) return;
    setImporting(true);
    try {
      const res = await invoke("workgroup_pick_recipe", {
        ...(connectionId ? { connectionId } : {}),
      });
      if (!res) return;
      setRecipeYaml(res.yaml);
      setRecipeMeta(res.meta);
      setBriefing(res.meta?.briefing || "");
      setParamValues(
        Object.fromEntries(Object.keys(res.meta?.params || {}).map((k) => [k, ""])),
      );
      setInputValues(
        Object.fromEntries(Object.keys(res.meta?.inputs || {}).map((k) => [k, ""])),
      );
    } catch (e) {
      notify({ message: `import failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setImporting(false);
    }
  }

  function clearRecipe() {
    setRecipeYaml(null);
    setRecipeMeta(null);
    setParamValues({});
    setInputValues({});
    setBriefing("");
  }

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
      if (isRecipe) {
        const res = await invoke("workgroup_launch_recipe", {
          profile: recipeHub,
          yaml: recipeYaml,
          recipeId: recipeMeta?.id || "recipe",
          params: Object.fromEntries(
            Object.entries(paramValues).map(([k, v]) => [k, v.trim()]),
          ),
          briefing: briefing.trim() || null,
          inputs: Object.fromEntries(
            Object.entries(inputValues).filter(([, v]) => v.trim().length > 0),
          ),
          ...(connectionId ? { connectionId } : {}),
        });
        notify({ message: `Launched from recipe ${recipeMeta?.id || ""}`, variant: "success" });
        onCreated?.(res?.workgroup_id, recipeHub);
      } else {
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
      }
    } catch (e) {
      notify({
        message: `${isRecipe ? "launch" : "create"} failed: ${String(e)}`,
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
          <div className={styles.recipeHead}>
            <Eyebrow>{isRecipe ? "HUB — FROM RECIPE" : "HUB"}</Eyebrow>
            {isRecipe ? (
              <Button variant="ghost" size="sm" onClick={clearRecipe} disabled={busy}>
                Clear recipe
              </Button>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                loading={importing}
                onClick={pickRecipe}
              >
                Import recipe…
              </Button>
            )}
          </div>
          {isRecipe ? (
            <div className={styles.recipeHub}>
              <Diamond color={hub?.accent} /> @{profileLabel(recipeHub)}
              <span className={styles.recipeName}>· {recipeMeta?.name}</span>
            </div>
          ) : (
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
          )}
        </div>

        {!isRecipe && (
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
        )}

        {!isRecipe && (
          <div className={styles.field}>
            <Eyebrow>MEMBERS — PEERS OF @{profileLabel(hubProfile)}</Eyebrow>
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
        )}

        <div className={styles.field}>
          <Eyebrow>BRIEFING</Eyebrow>
          <Textarea
            className={`ds-field ${styles.growCap}`}
            rows={3}
            value={briefing}
            onChange={(e) => setBriefing(e.target.value)}
            placeholder="what is this workgroup about?"
          />
        </div>

        {!isRecipe && (
          <div className={styles.field}>
            <Eyebrow>PIPELINE (OPTIONAL)</Eyebrow>
            <Field
              value={pipeline}
              onChange={(e) => setPipeline(e.target.value)}
              placeholder="intake, content, build, qa"
            />
          </div>
        )}

        {isRecipe && (Object.keys(declaredParams).length > 0 || Object.keys(declaredInputs).length > 0) && (
          <div className={styles.sectionDivider}>
            <Eyebrow>RECIPE INPUTS</Eyebrow>
          </div>
        )}

        {isRecipe && Object.entries(declaredParams).map(([k, spec]) => (
          <div className={styles.field} key={`param-${k}`}>
            <Eyebrow>{k.toUpperCase()}</Eyebrow>
            <Field
              value={paramValues[k] || ""}
              onChange={(e) =>
                setParamValues((prev) => ({ ...prev, [k]: e.target.value }))
              }
              placeholder={spec.pattern || "value"}
              spellCheck={false}
            />
          </div>
        ))}

        {isRecipe && Object.entries(declaredInputs).map(([k, spec]) => (
          <div className={styles.field} key={`input-${k}`}>
            <Eyebrow>{(spec.label || k).toUpperCase()}{spec.required ? "" : " (OPTIONAL)"}</Eyebrow>
            <Textarea
              className={`ds-field ${styles.growCap}`}
              rows={4}
              value={inputValues[k] || ""}
              onChange={(e) =>
                setInputValues((prev) => ({ ...prev, [k]: e.target.value }))
              }
              placeholder={spec.placeholder || `seeded into ${spec.dest || "the project"} before kickoff`}
            />
          </div>
        ))}

        <div className={styles.footer}>
          <DialogFooter
            onCancel={onClose}
            primaryLabel={isRecipe ? "Launch" : "Create"}
            primaryDisabled={!canSubmit}
            primaryLoading={busy}
            onPrimary={submit}
          />
        </div>
      </div>
    </Modal>
  );
}
