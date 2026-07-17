from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

JSON_COLLECTIONS = ("pages", "rooms", "amenities", "dining", "offers", "testimonials", "experiences")
MD_COLLECTIONS = ("posts",)
# legal/ is deliberately absent: hotel-supplied verbatim text, never machine-translated.

IMMUTABLE_KEYS = frozenset({
    "lang", "slug", "image", "gallery", "cover", "priceFrom", "currency",
    "order", "id", "map", "coords", "phone", "email", "url", "address",
    "featured", "keywords",
})
_SKIP_VALUE = re.compile(r"^(https?://|/|\+?\d[\d\s.-]*$|[\w.+-]+@[\w-]+\.)|\.(webp|jpe?g|png|svg)$")

LOCALE_HINTS = {
    "de": "formal Sie; compound nouns fine; keep length within ~30% of source",
    "fr": "formal vous; avoid Anglicisms (réservation, not booking)",
    "it": "mid-formal, warm not effusive",
    "en": "mid-Atlantic English, avoid US/UK-specific idioms",
    "pt": "Iberian Portuguese; warm, conversational",
    "nl": "direct, plain; avoid English loans where natural Dutch exists",
    "ca": "match the hotel's formality (vostè/tu)",
    "ru": "formal Вы; Cyrillic punctuation conventions",
    "zh-Hans": "concise, no Anglicisms; correct measure words",
}

MAX_BATCH_ENTRIES = 50
MAX_WORKERS = 3


def _is_translatable(key: str, value) -> bool:
    if not isinstance(value, str) or key in IMMUTABLE_KEYS:
        return False
    v = value.strip()
    if len(v) < 2 or not re.search(r"[A-Za-zÀ-ÿ]", v):
        return False
    return not _SKIP_VALUE.search(v)


def _walk(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                yield from _walk(v, path + (k,))
            elif _is_translatable(k, v):
                yield path + (k,), v
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, (dict, list)):
                yield from _walk(v, path + (i,))
            elif isinstance(v, str) and _is_translatable("", v):
                yield path + (i,), v


def _set_path(node, path, value):
    for p in path[:-1]:
        node = node[p]
    node[path[-1]] = value


def _split_frontmatter(text: str) -> tuple[dict, str, str] | None:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return None
    import yaml
    front = yaml.safe_load(m.group(1)) or {}
    return front, m.group(0), text[m.end():]


def _model_kwargs():
    from alpi import config as cfg_mod
    home = Path(os.environ["ALPI_HOME"])
    cfg = cfg_mod.load(home)
    return cfg_mod.resolve_model(cfg)


def translate_batch(call_kwargs: dict, target: str, mapping: dict[str, str], brand: str) -> dict[str, str]:
    """One LLM call: {id: source} -> {id: translated}. Module-level so tests can stub the model boundary."""
    from alpi import llm

    hint = LOCALE_HINTS.get(target, "")
    system = (
        f"You are a hotel-website translator. Translate every value of the JSON "
        f"object from its source language into '{target}'. {hint}\n"
        f"Hotel: {brand}. Rules: adapt to native idiom, never transliterate; "
        "facts (numbers, distances, proper nouns, the hotel's own-language room "
        "names) stay verbatim; no Anglicisms where a native word exists; return "
        "ONLY a JSON object with exactly the same keys and translated values."
    )
    out = llm.complete(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(mapping, ensure_ascii=False)},
        ],
        **call_kwargs,
    )
    text = (out.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("model returned non-object JSON")
    return {str(k): str(v) for k, v in parsed.items()}


def _translate_leaves(call_kwargs, target, leaves: dict[str, str], brand: str) -> tuple[dict[str, str], list[str]]:
    ids = list(leaves)
    result: dict[str, str] = {}
    for i in range(0, len(ids), MAX_BATCH_ENTRIES):
        chunk = {k: leaves[k] for k in ids[i:i + MAX_BATCH_ENTRIES]}
        try:
            result.update(translate_batch(call_kwargs, target, chunk, brand))
        except Exception:  # noqa: BLE001
            result.update(translate_batch(call_kwargs, target, chunk, brand))
    # One targeted retry for multi-word leaves that came back identical — untranslated fields, not proper nouns.
    suspicious = {
        k: v for k, v in leaves.items()
        if result.get(k, "").strip() == v.strip() and " " in v.strip()
    }
    if suspicious:
        try:
            result.update(translate_batch(call_kwargs, target, suspicious, brand))
        except Exception:  # noqa: BLE001
            pass
    warnings = [
        f"{target}: leaf identical to source after retry: {leaves[k][:60]!r}"
        for k in suspicious
        if result.get(k, "").strip() == leaves[k].strip()
    ]
    missing = [k for k in leaves if not str(result.get(k, "")).strip()]
    if missing:
        raise SystemExit(f"TRANSLATE FAIL · {target}: model dropped {len(missing)} field(s)")
    return result, warnings


def _source_files(content_dir: Path, source: str) -> list[Path]:
    files: list[Path] = []
    for coll in JSON_COLLECTIONS:
        files.extend(sorted((content_dir / coll).glob(f"*.{source}.json")))
    for coll in MD_COLLECTIONS:
        files.extend(sorted((content_dir / coll).glob(f"*.{source}.md")))
    return files


def _target_path(src: Path, source: str, target: str) -> Path:
    return src.with_name(src.name.replace(f".{source}.", f".{target}."))


def _validate(content_dir: Path, source: str, targets: list[str]) -> tuple[int, list[str]]:
    errors: list[str] = []
    expected = 0
    for src in _source_files(content_dir, source):
        src_struct = None
        if src.suffix == ".json":
            src_struct = sorted(str(p) for p, _ in _walk(json.loads(src.read_text())))
        for t in targets:
            tp = _target_path(src, source, t)
            expected += 1
            if not tp.exists():
                errors.append(f"missing: {tp.name}")
                continue
            if tp.suffix == ".json":
                try:
                    data = json.loads(tp.read_text())
                except json.JSONDecodeError as e:
                    errors.append(f"invalid JSON: {tp.name} ({e})")
                    continue
                if data.get("lang") != t:
                    errors.append(f"wrong lang in {tp.name}: {data.get('lang')!r}")
                if sorted(str(p) for p, _ in _walk(data)) != src_struct:
                    errors.append(f"structure drift vs source: {tp.name}")
    return expected, errors


def run(project: Path, only: list[str] | None, check_only: bool) -> int:
    site = json.loads((project / "src" / "config" / "site.json").read_text())
    source = site.get("defaultLocale") or "es"
    targets = [l for l in site.get("locales", []) if l != source]
    if only:
        targets = [t for t in targets if t in only]
    if not targets:
        print("TRANSLATE OK · no target locales declared")
        return 0
    content_dir = project / "src" / "content"
    sources = _source_files(content_dir, source)
    if not sources:
        print(f"TRANSLATE FAIL · no source ({source}) entries under {content_dir}")
        return 1

    if not check_only:
        call_kwargs = _model_kwargs()
        brand = str((site.get("brand") or {}).get("name") or project.name)
        all_warnings: list[str] = []

        def _one_locale(target: str) -> list[str]:
            leaves: dict[str, str] = {}
            index: dict[str, tuple[Path, object]] = {}
            for src in sources:
                if src.suffix == ".json":
                    data = json.loads(src.read_text())
                    for path, value in _walk(data):
                        key = f"{src.name}§{'/'.join(map(str, path))}"
                        leaves[key] = value
                        index[key] = (src, path)
                else:
                    split = _split_frontmatter(src.read_text())
                    if split is None:
                        continue
                    front, _, body = split
                    for fkey in ("title", "excerpt"):
                        if front.get(fkey):
                            leaves[f"{src.name}§front:{fkey}"] = str(front[fkey])
                    leaves[f"{src.name}§body"] = body.strip()
            translated, warnings = _translate_leaves(call_kwargs, target, leaves, brand)
            for src in sources:
                tp = _target_path(src, source, target)
                if src.suffix == ".json":
                    data = copy.deepcopy(json.loads(src.read_text()))
                    for path, _ in list(_walk(data)):
                        key = f"{src.name}§{'/'.join(map(str, path))}"
                        _set_path(data, path, translated[key])
                    data["lang"] = target
                    tp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                else:
                    import yaml
                    split = _split_frontmatter(src.read_text())
                    front, _, _ = split
                    front = dict(front)
                    for fkey in ("title", "excerpt"):
                        k = f"{src.name}§front:{fkey}"
                        if k in translated:
                            front[fkey] = translated[k]
                    front["lang"] = target
                    body = translated.get(f"{src.name}§body", "")
                    tp.write_text(f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False)}---\n\n{body}\n")
            return warnings

        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(targets))) as ex:
            for w in ex.map(_one_locale, targets):
                all_warnings.extend(w)
    else:
        all_warnings = []

    expected, errors = _validate(content_dir, source, targets)
    if errors:
        print(f"TRANSLATE FAIL · {len(errors)} error(s):")
        for e in errors[:20]:
            print("  -", e)
        return 1
    for w in all_warnings[:20]:
        print("  ⚠", w)
    print(
        f"TRANSLATE OK · {len(sources)} source × {len(targets)} locales = "
        f"{expected} files verified · {len(all_warnings)} warning(s)"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="project dir; relative resolves against ALPI_WORKSPACE")
    ap.add_argument("--only", action="append", default=None, help="limit to locale (repeatable)")
    ap.add_argument("--check", action="store_true", help="validate existing targets, write nothing")
    args = ap.parse_args()
    project = Path(args.project)
    if not project.is_absolute():
        project = Path(os.environ.get("ALPI_WORKSPACE", ".")) / project
    if not project.exists():
        print(f"TRANSLATE FAIL · project not found: {project}")
        return 1
    return run(project, args.only, args.check)


if __name__ == "__main__":
    sys.exit(main())
