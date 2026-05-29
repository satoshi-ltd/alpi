"""Seed one initial #task per company standing workgroup, hub-side, so the org has live conversations right after `organizations/setup.py company`. Idempotent — rerunning preempts the open task with the same canonical text."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from setup import (  # noqa: E402
    PROFILES_DIR,
    _latest_wg_dir,
    fail,
    init_org,
    load_workgroups,
    ok,
    run,
    step,
    warn,
)

init_org("company")


TASKS: dict[str, str] = {
    "roadmap": (
        "#task #h2-product-bets H2 product bets across SplitPass, Clonara and Money\n"
        "\n"
        "We have engineering capacity for three significant bets across "
        "our three own-software products next half. Frame each candidate "
        "as a hypothesis with a metric and a 30-day kill criterion — not "
        "a feature list, a set of testable bets. Engagement work (the "
        "consultancy side) stays its own pipeline; this task is about what "
        "we ship under our own name to keep proving we eat the dog food.\n"
        "\n"
        "Vera — strategic frame: which of the three products earns the "
        "next concentrated investment, and what do we explicitly defer? "
        "Saying no is as much the deliverable as saying yes. Zeta — flag "
        "any bet whose cryptographic surface or on-device constraint hides "
        "real cost (Clonara's grounded-memory store, SplitPass's shard "
        "envelope versioning, Money's AsyncStorage migration story), and "
        "any whose rollback path through the app stores isn't clean. "
        "Echo — for each candidate, sketch the growth angle within "
        "Satoshi's posture: who is it for, how do they find us without "
        "ad networks or telemetry, and what does success look like in 90 "
        "days (Clonara installs, SplitPass GitHub stars, Money active "
        "devices — pick the one metric that actually matters for that bet).\n"
        "\n"
        "Deliverable: three bet titles, each with hypothesis + metric + "
        "kill criterion + owner. I'll #done when the ranked list is locked."
    ),
    "architecture": (
        "#task #adr-reproducible-builds design the unified reproducible-build policy across the three apps\n"
        "\n"
        "We promise auditable receipts and reproducible builds. SplitPass, "
        "Clonara and Money each carry their own ad-hoc build story today. "
        "This task DESIGNS the shared policy from first principles — we'll "
        "audit the existing pipelines and migrate per-app in follow-up "
        "tasks. The goal here is a legible ADR an external auditor (or a "
        "future-us reading cold) can hold against any release: what's "
        "pinned, who signs, where the SBOM lives, how the chain is "
        "verifiable without trusting us.\n"
        "\n"
        "Forge — from first principles + your memory of these stacks "
        "(React Native + Tauri + Python daemon), propose the canonical "
        "shape: deps + lockfile policy, signing-key custody model (HSM "
        "vs per-app vs rotation cadence — pick one and defend it), SBOM "
        "format + location, build-attestation chain. Be concrete (\"the "
        "lockfile is pinned by SHA, regenerated only by\"…), don't hand-"
        "wave. If a specific app has a constraint that breaks the policy, "
        "name the app and the constraint — that's a follow-up task, not "
        "a reason to weaken the policy.\n"
        "\n"
        "Sentinel — the audit view: write the procedure an external "
        "third party follows from source commit to binary in TestFlight "
        "/ Play Internal without taking our word for anything. Reproduce-"
        "from-scratch steps, expected output hashes, what's signed vs "
        "what's witnessed. Flag the gaps in our current toolchain that "
        "would make any step impossible to verify today — those become "
        "concrete sub-tasks for a follow-up.\n"
        "\n"
        "Deliverable: an ADR (context · decision · rejected alternatives "
        "· consequences) plus a follow-up task list, one per per-app "
        "migration. #done when the ADR is locked and the follow-up "
        "tasks have owners + targets. Implementation lands separately, "
        "per app."
    ),
    "growth": (
        "#task #icp-v2-consultancy ICP v2 for consultancy engagements — who do we say no to?\n"
        "\n"
        "We take on a handful of engagements a year, senior-only, no "
        "outbound. The site says \"founders, security teams or regulated "
        "operators who can't afford a leak and won't ship surveillance\" — "
        "that's the story. We need the operational version so the next "
        "twelve inbound calls arrive closer to qualified, and the ones "
        "that aren't a fit bounce off the engage page instead of our "
        "calendar. Our pipeline DB is empty post-bootstrap, so this round "
        "is from-first-principles + posture, not from engagement history. "
        "Once Rex has been logging deals for a quarter we'll do a "
        "data-driven v3.\n"
        "\n"
        "Rex — design the qualifying rubric from Satoshi's posture + "
        "your operating memory: company shape (stage, vertical, "
        "regulator exposure), trigger events that bring real buyers to "
        "us (incident? compliance deadline? new CISO?), patterns that "
        "signal tire-kicker (no internal champion? wants a vendor not a "
        "partner? wants telemetry?). Output is the rubric, not the "
        "data — six to ten signals each side of the line.\n"
        "\n"
        "Quill — based on Rex's rubric, rewrite satoshi-ltd.com/engage "
        "in three variants. Specific to Satoshi voice (no \"synergy\", "
        "no \"transformative\", no \"enterprise-grade\"); each variant "
        "says yes to one winning shape and visibly signals no to the "
        "wasters. If satoshi-ltd.com/engage isn't in your workspace yet, "
        "ask vera for the current copy and proceed from there.\n"
        "\n"
        "Deliverable: a one-page ICP v2 rubric (signals + rationale "
        "per side of the line) plus three engage-page variants ready "
        "for review. #done when the rubric is locked and the three "
        "variants are ready — going live to satoshi-ltd.com/engage is "
        "a follow-up that flows through forge."
    ),
    "customers": (
        "#task #onboarding-friction-framework framework for surfacing onboarding friction without telemetry\n"
        "\n"
        "Clonara and Money are where most real user contact lives — "
        "SplitPass skews to a technical audience that won't open a ticket. "
        "We don't ingest App Store / Play reviews, support email or "
        "Clonara's optional lead email into the workspace today — that "
        "infrastructure doesn't exist yet. So this task is NOT a list of "
        "frictions; we don't have the data. The task is the FRAMEWORK "
        "we'll use to surface frictions once the channels are wired. "
        "Implementation of the ingestion is a separate task that flows "
        "out of this one to flux / forge.\n"
        "\n"
        "Hub — propose the framework given Satoshi's no-telemetry "
        "constraint. Specifics over generic. One paragraph per source "
        "channel (App Store reviews · Play reviews · support email · "
        "Clonara lead email): what we read, what cadence, what a "
        "\"signal vs noise\" threshold looks like for each, what the "
        "cluster taxonomy is (by user goal — what the user was trying "
        "to do — not by tag), the minimum sample before a pattern "
        "qualifies as evidence. Acknowledge explicitly: hub does not "
        "have the tooling wired to do this analysis today; this is the "
        "design we'll execute once it is.\n"
        "\n"
        "Fern — challenge weak signals + undefined thresholds. Decide "
        "which parts of the framework graduate to a flux task (wiring "
        "the ingestion) and which stay as ongoing hub responsibility. "
        "If hub's proposal hand-waves on a source, push for specifics "
        "or cut that source from v1.\n"
        "\n"
        "Deliverable: framework doc with source list + cadence + "
        "thresholds + sampling rule + cluster taxonomy. #done when the "
        "framework is locked. The follow-up — wiring the channels into "
        "workspace + running the first analysis — is a separate task."
    ),
}


def post_task(hub: str, wg_id: str, text: str) -> None:
    """Post a workgroup #task via the hub's CLI; surfaces stderr verbatim on failure."""
    res = run(["alpi", "-p", hub, "workgroup", "post", wg_id, text])
    if res.returncode != 0:
        msg = (res.stderr or res.stdout or "").strip() or "unknown error"
        fail(f"{hub} → post on {wg_id[:12]}…: {msg}")


def main() -> int:
    workgroups = load_workgroups()
    missing = [w["name"] for w in workgroups if w["name"] not in TASKS]
    if missing:
        warn(f"no #task copy defined for: {', '.join(missing)} — skipping those")

    step(f"opening {sum(1 for w in workgroups if w['name'] in TASKS)} workgroup task(s)")

    for spec in workgroups:
        name = spec["name"]
        hub = spec["hub"]
        if name not in TASKS:
            continue

        wg_dir = _latest_wg_dir(hub)
        if wg_dir is None:
            fail(
                f"{hub} has no workgroups under "
                f"{PROFILES_DIR / hub / 'alp' / 'workgroups'}; "
                f"run setup.py first",
            )
        wg_id = wg_dir.name

        post_task(hub, wg_id, TASKS[name])
        members = ", ".join(spec["members"]) or "(no members)"
        ok(f"{name:<14}  hub={hub}  wg={wg_id[:12]}…  → {members}")
        time.sleep(0.2)

    print()
    print(f"{len(TASKS)} task(s) opened. Run `alpi daemon logs` to watch members respond.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
