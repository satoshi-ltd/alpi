"""Walk the ALP workgroup protocol on `bench`, strictly single-task.

The driver is the same in both modes: open ONE task, then **listen** to the
workgroup (read + fold the transcript) until a hub `#done` closes it, and only
then open the next. Never preempts, never overlaps — the protocol is
single-task and the listener enforces it structurally.

  suite (default)  the script drives mind/scribe/tally/probe itself with fixed
                   text — no LLM turns — asserts each invariant, posts the
                   closing #done, then waits to READ that #done back before the
                   next task. Fast, deterministic, repeatable. Posts are real,
                   so markers render in the apps.

  live             the script only seeds each task as the hub, then waits for
                   the REAL agents to converge and mind to post #done before
                   seeding the next. Slower, non-deterministic — for watching
                   #working / #skip / #done render live in the apps.

Both reset the bench first (--no-reset to skip): remove + recreate the
workgroup (members rejoin) so every run starts on an empty transcript.

Preemption (a new #task closing the old) is the one rule the listener can't
cover — it is, by definition, opening the next task without a #done. It is
verified separately, not here.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from setup import (  # noqa: E402
    BLUE,
    GREEN,
    GREY,
    PROFILES_DIR,
    RED,
    RESET,
    YELLOW,
    _latest_wg_dir,
    fail,
    init_org,
    load_workgroups,
    run,
    setup_workgroups,
)

init_org("lab")

HUB = "mind"
WG_ID = ""
RESULTS: list[bool] = []
LISTEN_TIMEOUT_SUITE = 20

SUB = "I'd commit to tabs — it survives a skim and the cost is one config line."
SUB2 = "Two options, one axis: reader-effort vs writer-effort. Reader wins, so tabs."
SUB3 = "Checked three style guides: all default the same way — the evidence backs tabs."


def post(profile: str, text: str):
    return run(["alpi", "-p", profile, "workgroup", "post", WG_ID, text])


def rec(label: str, ok: bool, detail: str) -> None:
    mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    print(f"  {mark} {label:<38} {GREY}{detail}{RESET}")
    RESULTS.append(ok)


def reject(label: str, profile: str, text: str, substr: str) -> None:
    r = post(profile, text)
    if r.returncode == 0:
        rec(label, False, f"expected reject (~{substr!r}) but it was ACCEPTED")
        return
    out = (r.stderr + r.stdout).lower()
    if substr.lower() in out:
        rec(label, True, f"rejected · {substr}")
    else:
        rec(label, False, f"rejected but message lacked {substr!r}: {(r.stderr + r.stdout).strip()[:110]}")


def accept(label: str, profile: str, text: str) -> None:
    r = post(profile, text)
    ok = r.returncode == 0
    rec(label, ok, "accepted" if ok else f"rejected: {(r.stderr + r.stdout).strip()[:110]}")


def log(msg: str) -> None:
    print(f"\n{BLUE}{msg}{RESET}")


def wg_cmd(profile: str, *args: str):
    return run(["alpi", "-p", profile, "workgroup", *args])


def cmd_ok(label: str, profile: str, *args: str) -> None:
    r = wg_cmd(profile, *args)
    rec(label, r.returncode == 0, "ok" if r.returncode == 0 else f"failed: {(r.stderr + r.stdout).strip()[:100]}")


def cmd_reject(label: str, profile: str, args: tuple[str, ...], substr: str) -> None:
    r = wg_cmd(profile, *args)
    if r.returncode == 0:
        rec(label, False, "expected reject but it was ACCEPTED")
        return
    out = (r.stderr + r.stdout).lower()
    rec(label, substr.lower() in out, f"rejected · {substr}" if substr.lower() in out else f"wrong msg: {(r.stderr + r.stdout).strip()[:100]}")


# --- transcript folding + the listener (hub-side, no network; all v1) --------

def _fold():
    from alpi.alp import tasks as tasks_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.alp.workgroup import _read_transcript, _wg_dir

    home = PROFILES_DIR / HUB
    wg = wg_mod.load(home, WG_ID)
    kp = load_or_generate(home)
    own = wg.member(kp.pubkey_b64())
    group_key = wg_mod.open_sealed_group_key(own.sealed_key, kp)

    entries = _read_transcript(_wg_dir(home, WG_ID))
    events = []
    for entry in entries:
        if int(entry.get("key_version", 1)) != own.key_version:
            continue
        try:
            text = wg_mod.decrypt_post(
                group_key, entry["nonce"], entry["ciphertext"],
            ).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        events += tasks_mod.parse_post(
            text, int(entry.get("seq", 0)), str(entry.get("from", "")),
            hub_pubkey=wg.meta.hub_pubkey,
        )
    return tasks_mod.fold_tasks(events), len(entries)


def _active_slug() -> str | None:
    tasks, _ = _fold()
    for t in tasks:
        if getattr(t, "closed_seq", None) is None:
            return t.slug
    return None


def _closed_result(slug: str) -> str | None:
    tasks, _ = _fold()
    for t in tasks:
        if t.slug == slug and getattr(t, "closed_seq", None) is not None:
            return t.result or ""
    return None


def _latest_text() -> str:
    """Decrypted plaintext of the last transcript entry (current key version)."""
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.alp.workgroup import _read_transcript, _wg_dir

    home = PROFILES_DIR / HUB
    wg = wg_mod.load(home, WG_ID)
    kp = load_or_generate(home)
    own = wg.member(kp.pubkey_b64())
    group_key = wg_mod.open_sealed_group_key(own.sealed_key, kp)
    for entry in reversed(_read_transcript(_wg_dir(home, WG_ID))):
        if int(entry.get("key_version", 1)) != own.key_version:
            continue
        try:
            return wg_mod.decrypt_post(
                group_key, entry["nonce"], entry["ciphertext"],
            ).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
    return ""


def member_done_stripped(label: str, profile: str, text: str) -> None:
    """A member `#done`+handoff lands with the hub-only marker stripped, the
    handoff text preserved — the post is never a close (parser ignores it)."""
    from alpi.alp import tasks as tasks_mod
    r = post(profile, text)
    if r.returncode != 0:
        rec(label, False, f"rejected: {(r.stderr + r.stdout).strip()[:90]}")
        return
    stored = _latest_text()
    handoff = tasks_mod.strip_done_marker(text).strip()
    ok = "#done" not in stored and handoff and handoff in stored
    rec(label, bool(ok),
        f"stored {stored[:46]!r} · #done stripped" if ok
        else f"marker survived or handoff lost: {stored[:70]!r}")


def await_done(slug: str, timeout: int, tick: float, heartbeat: bool) -> tuple[bool, str | None]:
    """Read the workgroup until a hub #done closes `slug` (result != preempted)."""
    deadline = time.time() + timeout
    last_n = -1
    while time.time() < deadline:
        if _active_slug() != slug:
            res = _closed_result(slug)
            if res is not None and not res.lower().startswith("preempt"):
                return True, res
        if heartbeat:
            _, n = _fold()
            if n != last_n:
                print(f"    {GREY}… {n} posts so far, waiting for mind to #done #{slug}{RESET}")
                last_n = n
        time.sleep(tick)
    return False, None


def done_then_listen(slug: str, text: str) -> None:
    """Post the closing #done, then confirm by reading it back before the next task."""
    accept(f"close #{slug} (#done)", HUB, text)
    ok, res = await_done(slug, LISTEN_TIMEOUT_SUITE, 0.4, heartbeat=False)
    rec("listener: #done read before next task", ok,
        f"#{slug} closed · {(res or '')[:46]!r}" if ok else f"no #done for #{slug} after {LISTEN_TIMEOUT_SUITE}s")


# --- reset -------------------------------------------------------------------

def reset_bench() -> None:
    log("Reset · removing + recreating the bench (empty transcript)")
    wg_root = PROFILES_DIR / HUB / "alp" / "workgroups"
    if wg_root.exists():
        for d in sorted(p for p in wg_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
            try:
                run(["alpi", "-p", HUB, "workgroup", "remove", d.name, "--yes"],
                    stdin=subprocess.DEVNULL, timeout=30)
            except subprocess.TimeoutExpired:
                pass
    setup_workgroups(load_workgroups())


# --- deterministic suite -----------------------------------------------------

def run_suite() -> int:
    print(f"{BLUE}=== Protocol Lab · single-task suite on {WG_ID[:14]}… ==={RESET}")
    print(f"{GREY}one task at a time; listener reads the #done back before opening the next{RESET}")

    log("Phase 0 · rejects on an empty bench (none of these open a task)")
    reject("empty-post-rejected", HUB, "   ", "empty post")
    reject("task-slug-required", HUB, "#task plain text with no slug", "task-missing-slug")
    reject("member-cannot-open-task", "scribe", "#task #sneaky member opens a task", "only the workgroup hub")
    reject("hub-cannot-skip", HUB, "#skip not my job as hub", "hub-cannot-skip")
    reject("hub-cannot-working", HUB, "#working hub doesn't heartbeat", "hub-cannot-working")

    log("Task 1 · #memo-indent — happy path (full quorum) + in-task rule checks")
    accept("open #memo-indent", HUB, "#task #memo-indent decide the memo indent: tabs or spaces")
    reject("premature-#done-blocked", HUB, "#done closing with no peer input", "closure-quorum")
    reject("hub-no-back-to-back", HUB, "and here is my own second take", "turn-rotation")
    accept("scribe substantive", "scribe", SUB)
    time.sleep(1.2)
    reject("member-one-post-per-round", "scribe", SUB2, "turn-rotation")
    accept("tally substantive", "tally", SUB2)
    accept("probe substantive", "probe", SUB3)
    done_then_listen("memo-indent", "#done locked: tabs — reader-effort wins the axis")

    log("Task 2 · #h1-caps — #skip counts toward quorum (and renders its reason)")
    accept("open #h1-caps", HUB, "#task #h1-caps decide the H1 capitalisation")
    accept("scribe substantive", "scribe", "Title Case for the H1 — it reads as a heading, not a sentence.")
    accept("tally #skip (reason shown)", "tally", "#skip no structural tradeoff to map here")
    accept("probe #skip (reason shown)", "probe", "#skip nothing external to verify on capitalisation")
    done_then_listen("h1-caps", "#done locked: Title Case (1 substantive + 2 skips = quorum)")

    log("Task 3 · #footer-text — all-skip is degenerate, one substantive unblocks it")
    accept("open #footer-text", HUB, "#task #footer-text decide the footer disclaimer wording")
    accept("scribe #skip (bare, no reason)", "scribe", "#skip")
    accept("tally #skip (reason shown)", "tally", "#skip no tradeoff to structure on a fixed disclaimer")
    accept("probe #skip (reason shown)", "probe", "#skip nothing external to verify here")
    reject("all-skip blocks #done", HUB, "#done can't close on three skips", "closure-quorum")
    accept("hub reframes (opens a new round)", HUB, "Reframe: pick the shortest compliant line and defend it.")
    time.sleep(0.8)
    accept("scribe substantive (unblocks)", "scribe", "Shortest safe line: '© 2026 — all rights reserved.'")
    done_then_listen("footer-text", "#done locked: shortest compliant footer line")

    log("Task 4 · #cite-cwv — #working is rotation-exempt and doesn't satisfy quorum alone")
    accept("open #cite-cwv", HUB, "#task #cite-cwv should memos cite live Core Web Vitals numbers")
    accept("probe #working", "probe", "#working pulling Google's current CWV thresholds")
    accept("scribe substantive", "scribe", SUB)
    accept("tally substantive", "tally", SUB2)
    reject("#working alone blocks #done", HUB, "#done probe only signalled working", "closure-quorum")
    accept("probe substantive after #working", "probe", "Confirmed: LCP 'good' ≤ 2.5s — cite it, refresh quarterly.")
    done_then_listen("cite-cwv", "#done locked: cite the number, refresh quarterly")

    log("Task 5 · #done from a member is a handoff, never a close (marker stripped)")
    accept("open #adr-9", HUB, "#task #adr-9 ratify the build-pipeline ADR")
    member_done_stripped("member #done kept as handoff", "scribe",
                         "#done my section is ready — handing the build notes to mind")
    rec("member #done left the task open", _active_slug() == "adr-9",
        f"active={_active_slug()!r} (member can't close)")
    accept("tally substantive", "tally", SUB2)
    accept("probe substantive", "probe", SUB3)
    done_then_listen("adr-9", "#done locked: ADR-9 ratified — the handoff never closed it")

    passed, total = sum(RESULTS), len(RESULTS)
    color = GREEN if passed == total else RED
    print(f"\n{color}{passed}/{total} protocol assertions verified{RESET}")
    if passed != total:
        print(f"{YELLOW}note: failures usually mean an agent poller posted mid-check — re-run (reset is automatic).{RESET}")
    return 0 if passed == total else 1


# --- stress (edge cases the narrative suite doesn't reach) -------------------

def chk_budget() -> None:
    """In-process check of the workgroup lifetime budget gate — the CLI can't declare a cost, so we exercise _gate_post directly."""
    from alpi.alp import server as alp_server
    from alpi.alp.workgroup import Meta, _gate_post

    meta = Meta(id="t", name="t", hub_pubkey="t", created_at="t", budget={"max_usd": 0.10})
    within = True
    try:
        _gate_post(meta, {"usd": 0.0}, {"usd": 0.05})
    except Exception:  # noqa: BLE001
        within = False
    rec("budget-gate: within cap admits", within, "declare 0.05 against a 0.10 cap → ok")

    breached = False
    try:
        _gate_post(meta, {"usd": 0.09}, {"usd": 0.05})
    except alp_server.HandlerError as e:  # noqa: BLE001
        breached = getattr(e, "code", None) == -32005 or "budget" in str(e).lower()
    except Exception as e:  # noqa: BLE001
        breached = "budget" in str(e).lower()
    rec("budget-gate: breach → -32005", breached, "0.09 used + 0.05 declared > 0.10 cap → rejected")


def chk_leave_rekey() -> None:
    """Member leaves → group key rotates; ex-member's old key can't read new traffic but can still read old (forward secrecy)."""
    from alpi.alp import subscription as sub_mod
    from alpi.alp import workgroup as wg_mod
    from alpi.alp.keys import load_or_generate
    from alpi.alp.workgroup import _read_transcript, _wg_dir

    mind_home = PROFILES_DIR / HUB
    probe_home = PROFILES_DIR / "probe"
    probe_kp = load_or_generate(probe_home)
    probe_pk = probe_kp.pubkey_b64()

    sub = sub_mod.get(probe_home, WG_ID)
    if sub is None or sub.latest_version() == 0:
        rec("leave-rekey: precondition", False, "probe has no cached group key")
        return
    v_old = sub.latest_version()
    gk_old = wg_mod.open_sealed_group_key(sub.sealed_for(v_old), probe_kp)

    entries_before = _read_transcript(_wg_dir(mind_home, WG_ID))
    old_readable = False
    if entries_before:
        e = entries_before[-1]
        try:
            wg_mod.decrypt_post(gk_old, e["nonce"], e["ciphertext"])
            old_readable = True
        except Exception:  # noqa: BLE001
            old_readable = False

    cmd_ok("probe leaves the workgroup", "probe", "leave", WG_ID)

    wg = wg_mod.load(mind_home, WG_ID)
    v_new = wg.meta.current_key_version
    dropped = wg.member(probe_pk) is None
    resealed = bool(wg.members) and all(m.key_version == v_new for m in wg.members)
    rec("leave rotates the group key", dropped and v_new == v_old + 1 and resealed,
        f"v {v_old}→{v_new}, probe dropped={dropped}, remaining resealed={resealed}")

    accept("hub posts new traffic under the new key", HUB, "New traffic after the rekey — only current members can read this")
    new_entry = _read_transcript(_wg_dir(mind_home, WG_ID))[-1]
    new_blocked = False
    try:
        wg_mod.decrypt_post(gk_old, new_entry["nonce"], new_entry["ciphertext"])
    except Exception:  # noqa: BLE001
        new_blocked = True
    rec("forward secrecy: ex-member can't read new traffic", new_blocked and old_readable,
        f"old post readable with old key={old_readable}, new post blocked={new_blocked}")

    cmd_ok("hub re-adds probe", HUB, "add-member", WG_ID, probe_pk)
    cmd_ok("probe rejoins (bench restored)", "probe", "join", HUB, WG_ID)


def chk_timeout_escape() -> None:
    """All-skip blocks #done until the 10-minute hard timeout; then the hub may close. Slow — watches the real hub decide."""
    accept("open #timeout-escape", HUB, "#task #timeout-escape a question with no contributor")
    accept("scribe #skip", "scribe", "#skip")
    accept("tally #skip", "tally", "#skip")
    accept("probe #skip", "probe", "#skip")
    reject("all-skip blocks #done before timeout", HUB, "#done premature on an all-skip task", "closure-quorum")
    print(f"    {GREY}waiting up to ~11 min — watching whether mind closes it after the 10-min escape…{RESET}")
    ok, res = await_done("timeout-escape", timeout=700, tick=15, heartbeat=True)
    if ok:
        rec("timeout escape: hub closed after ~10 min", True, f"hub auto-#done: {(res or '')[:46]!r}")
    else:
        accept("force #done after the timeout", HUB, "#done via the 10-minute escape")
        ok2, _ = await_done("timeout-escape", 20, 0.4, heartbeat=False)
        rec("timeout escape: #done admitted past 10 min", ok2, "quorum bypassed after 600s")


def run_stress(slow: bool) -> int:
    print(f"{BLUE}=== Protocol Lab · stress on {WG_ID[:14]}… ==={RESET}")
    print(f"{GREY}edge cases the narrative suite doesn't reach: recognition, preemption, pause, budget, rekey{RESET}")

    log("Recognition · line-start + #done-on-empty rules")
    accept("mid-sentence #task stays prose", HUB, "I'll open a #task about this later, not now")
    rec("…opened no task", _active_slug() is None, f"active={_active_slug()}")
    accept("member spacer", "scribe", "noted, nothing to add yet")
    accept("#done on an empty slot (no-op)", HUB, "#done nothing is open to close")
    rec("…still no task", _active_slug() is None, f"active={_active_slug()}")

    log("Preemption · a new #task closes the old, then close cleanly")
    accept("open #pre-a", HUB, "#task #pre-a first question")
    accept("open #pre-b (preempts #pre-a)", HUB, "#task #pre-b supersedes the first")
    slug, res = _active_slug(), _closed_result("pre-a") or ""
    rec("#pre-b active, #pre-a preempted", slug == "pre-b" and "preempt" in res.lower(),
        f"active=#{slug}, #pre-a closed as {res!r}")
    accept("scribe substantive", "scribe", SUB)
    accept("tally substantive", "tally", SUB2)
    accept("probe substantive", "probe", SUB3)
    done_then_listen("pre-b", "#done locked the superseding question")

    log("Pause / resume · post blocked (-32010), pull works, hub-only")
    cmd_ok("hub pauses", HUB, "pause", WG_ID)
    reject("member post blocked while paused", "scribe", "trying to post while paused", "paused")
    cmd_ok("member pull still works while paused", "scribe", "pull", WG_ID)
    cmd_reject("member cannot pause (hub-only)", "tally", ("pause", WG_ID), "hub")
    cmd_ok("hub resumes", HUB, "resume", WG_ID)
    accept("member post works after resume", "scribe", "back online after resume")

    log("Budget · workgroup lifetime cap (-32005)")
    chk_budget()

    log("Leave + rekey · forward secrecy")
    chk_leave_rekey()

    if slow:
        log("All-skip → 10-minute quorum-timeout escape (slow)")
        chk_timeout_escape()
    else:
        print(f"\n{GREY}(skipped the 10-min quorum-timeout escape — pass --slow to run it){RESET}")

    passed, total = sum(RESULTS), len(RESULTS)
    color = GREEN if passed == total else RED
    print(f"\n{color}{passed}/{total} stress assertions verified{RESET}")
    if passed != total:
        print(f"{YELLOW}note: failures often mean an agent poller posted mid-check — re-run (reset is automatic).{RESET}")
    return 0 if passed == total else 1


# --- live (real agents) ------------------------------------------------------

LIVE_TASKS = [
    ("cite-cwv",
     "#task #cite-cwv Should our one-page memos cite Google's current 'good' "
     "LCP threshold for Core Web Vitals, and what is it?\n\n"
     "One call: hard-code the number in the template or link out. Bring your "
     "angle and I'll lock it."),
    ("opener-voice",
     "#task #opener-voice Verdict-first or context-first openers for our memos?\n\n"
     "One call, committed. Phrasing, tradeoff, or evidence — whatever your "
     "angle is."),
]


def run_live(timeout: int) -> int:
    print(f"{BLUE}=== Protocol Lab · live on {WG_ID[:14]}… ==={RESET}")
    print(f"{GREY}seeds one task; real agents work it; listener waits for mind's #done; then the next.{RESET}")
    print(f"{GREY}watch the bench in desktop / mobile to see #working / #skip / #done render.{RESET}")
    ok_all = True
    for slug, text in LIVE_TASKS:
        log(f"Seeding #{slug}")
        r = post(HUB, text)
        if r.returncode != 0:
            print(f"    {RED}✗{RESET} post failed: {(r.stderr + r.stdout).strip()[:110]}")
            return 1
        ok, res = await_done(slug, timeout, tick=6, heartbeat=True)
        if ok:
            print(f"    {GREEN}✓{RESET} {GREY}#{slug} closed by #done: {(res or '')[:60]!r}{RESET}")
        else:
            print(f"    {RED}✗{RESET} {GREY}timeout {timeout}s — #{slug} still open, stopping{RESET}")
            ok_all = False
            break
    print(f"\n{GREEN if ok_all else RED}live run {'complete' if ok_all else 'stopped'}{RESET}")
    return 0 if ok_all else 1


def resolve_wg() -> str:
    wg_dir = _latest_wg_dir(HUB)
    if wg_dir is None:
        fail(f"{HUB} has no workgroups; run `setup.py lab` first")
    return wg_dir.name


def main() -> int:
    global WG_ID
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--live", action="store_true", help="Seed tasks for the real agents to work (default: deterministic suite).")
    parser.add_argument("--stress", action="store_true", help="Edge-case suite: recognition, preemption, pause, budget, leave/rekey.")
    parser.add_argument("--slow", action="store_true", help="Modifier for --stress: also run the ~10-min quorum-timeout escape.")
    parser.add_argument("--no-reset", action="store_true", help="Skip the bench reset; append to the existing transcript.")
    parser.add_argument("--timeout", type=int, default=600, help="--live: seconds to wait for each task's #done (default 600).")
    args = parser.parse_args()

    if args.slow and not args.stress:
        fail("--slow is a modifier for --stress — run `--stress --slow`")
    if args.live and args.stress:
        fail("--live and --stress are mutually exclusive")

    if not args.no_reset:
        reset_bench()
    WG_ID = resolve_wg()

    if args.live:
        return run_live(args.timeout)
    if args.stress:
        return run_stress(args.slow)
    return run_suite()


if __name__ == "__main__":
    sys.exit(main())
