"""Open one #task per standing workgroup, hub-side. Companion to ``setup.py``; rerunning preempts the open task."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from setup import (  # noqa: E402
    PROFILES_DIR,
    _latest_wg_dir,
    fail,
    load_workgroups,
    ok,
    run,
    step,
    warn,
)


TASKS: dict[str, str] = {
    "roadmap": (
        "#task H2 product bets across SplitPass, Clonara and Money\n"
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
        "#task ADR — unified reproducible-build pipeline across the three apps\n"
        "\n"
        "We promise auditable receipts and reproducible builds. Right now "
        "SplitPass, Clonara and Money each carry their own ad-hoc build "
        "story. Decide and document the shared toolchain: how the build "
        "is pinned, who signs the artifacts, where the SBOM lives, and "
        "how an external third party can reproduce a release from the "
        "public reference-implementation repo without trusting us. The "
        "goal is a legible, reversible call we can stand behind the next "
        "time a regulated client asks us to prove the chain — not a "
        "perfect platform.\n"
        "\n"
        "Forge — operational reality: walk each app's current build "
        "end-to-end (deps, lockfiles, signing, store upload) and call out "
        "where a shared pipeline actually saves senior hours versus where "
        "it adds friction that won't survive a release crunch. Sentinel — "
        "the supply-chain view: dependency pinning policy, signing-key "
        "custody (HSM? per-app keys? rotation cadence?), what happens "
        "when a maintainer credential is compromised, and the concrete "
        "steps an external auditor follows from source commit to "
        "binary in TestFlight / Play Internal without taking our word "
        "for anything.\n"
        "\n"
        "Deliverable: an ADR with context, decision, rejected "
        "alternatives, and the migration path for each app. I'll #done "
        "when the ADR is merged and at least one product release has "
        "shipped through the new pipeline."
    ),
    "growth": (
        "#task ICP v2 for consultancy engagements — who do we say no to?\n"
        "\n"
        "We take on a handful of engagements a year, senior-only, no "
        "outbound. The site says \"founders, security teams or regulated "
        "operators who can't afford a leak and won't ship surveillance\" — "
        "that's the story. We need the operational version so the next "
        "twelve inbound calls arrive closer to qualified, and the ones "
        "that aren't a fit bounce off the engage page instead of our "
        "calendar.\n"
        "\n"
        "Rex — map our recent engagements (won, declined, and the "
        "tire-kickers who took two calls and vanished) against company "
        "shape: stage, vertical, regulator exposure, what the trigger "
        "was, who championed internally, what killed the no-fits. "
        "Pattern-match: where do we deliver asymmetric value versus "
        "where do we waste senior hours. Quill — based on Rex's read, "
        "rewrite satoshi-ltd.com/engage in three variants. Specific to "
        "Satoshi voice (no \"synergy\", no \"transformative\", no "
        "\"enterprise-grade\"); each variant says yes to one winning shape "
        "and visibly signals no to the wasters.\n"
        "\n"
        "Deliverable: a one-page ICP v2 plus three engage-page variants "
        "ready for A/B. I'll #done when one variant is live at "
        "satoshi-ltd.com/engage."
    ),
    "customers": (
        "#task Top three onboarding friction points across Clonara and Money\n"
        "\n"
        "Clonara and Money are where most real user contact lives — "
        "SplitPass skews to a more technical audience that won't open a "
        "ticket. We've been treating each report as a one-off; this task "
        "forces aggregation into the three biggest first-seven-day "
        "friction points across both apps, with a decision attached: "
        "ship a fix, or accept and document why. The frame is Satoshi's: "
        "zero telemetry constrains the data we have, so we lean on App "
        "Store / Play reviews, support email and Clonara's optional lead "
        "email — not on funnel analytics we deliberately don't ship. The "
        "constraint is a feature, not an excuse.\n"
        "\n"
        "Hub — pull tickets and reviews from the last 90 days across "
        "both apps, cluster by user goal (not by tag — by what the user "
        "was actually trying to do), and surface the top three frictions "
        "with frequency, locale spread where visible (Clonara ships in 15 "
        "locales incl. RTL), and severity evidence. For each, propose "
        "either a concrete fix (owner + date) or an explicit accept with "
        "a stated reason consistent with our privacy posture. I'll defend "
        "the user side and decide which go to engineering versus which we "
        "live with for now.\n"
        "\n"
        "Deliverable: ranked list of three frictions, each with a "
        "fix-or-accept decision and an owner. #done when every line has "
        "either an action or an accepted-with-rationale."
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
