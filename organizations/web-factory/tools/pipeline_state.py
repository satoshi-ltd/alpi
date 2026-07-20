from __future__ import annotations

from pathlib import Path

PHASES = ["intake", "assets", "content", "translation", "build", "qa"]


def _canonical_phase(slug: str) -> str | None:
    slug = (slug or "").lower()
    for phase in sorted(PHASES, key=len, reverse=True):
        if slug == phase or slug.startswith(phase + "-"):
            return phase
    return None


def derive_state(posts: list[dict], hub_pubkey: str) -> str | None:
    from alpi.alp import tasks as wg_tasks

    events = []
    for p in posts:
        events.extend(wg_tasks.parse_post(
            str(p.get("text") or ""), int(p.get("seq", 0)),
            str(p.get("from") or ""), hub_pubkey=hub_pubkey,
        ))
    folded = wg_tasks.fold_tasks(events)
    if not folded:
        return None
    last = folded[-1]
    phase = _canonical_phase(last.slug)
    if last.is_open:
        if last.slug.startswith("maint-"):
            return "maintenance"
        return phase or "iterating"
    result = (last.result or "").strip().upper()
    if result.startswith("BLOCKED"):
        return "blocked"
    if last.slug.startswith("maint-"):
        return "launched"
    if phase == PHASES[-1]:
        return "launched"
    if phase in PHASES:
        return PHASES[PHASES.index(phase) + 1]
    return None


def find_wg(home: Path, hub: str, slug: str) -> Path | None:
    import yaml

    root = home / "alp" / "workgroups"
    for d in (root.iterdir() if root.exists() else []):
        meta = d / "meta.yaml"
        if meta.exists() and (yaml.safe_load(meta.read_text()) or {}).get("name") == f"proj-{slug}":
            return d
    return None


def read_state(home: Path, hub: str, slug: str) -> tuple[str | None, str | None]:
    from alpi.alp import workgroup as wg_mod
    from alpi.service import _all_hub_posts_decrypted

    wg = find_wg(home, hub, slug)
    if wg is None:
        return None, None
    wg_obj = wg_mod.load(home, wg.name)
    posts = _all_hub_posts_decrypted(home, wg_obj)
    return wg.name, derive_state(posts, wg_obj.meta.hub_pubkey)
