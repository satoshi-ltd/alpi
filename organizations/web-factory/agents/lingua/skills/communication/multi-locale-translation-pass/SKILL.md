---
name: multi-locale-translation-pass
description: Replicate quill's source-locale content entries into every target locale in site.json — a scripted pass (scripts/run.py) does the file orchestration, parallel per-locale LLM batches, and mechanical field-coverage validation; lingua supplies judgment on the output, never hand-writes locale files.
category: communication
version: 0.4.0
origin: user
requires_env: [OPENROUTER_API_KEY]
tools: [read_file, search]
keywords: ['translation', 'i18n', 'localisation', 'multi-locale', 'voice-preservation']
created_at: 2026-05-29
---

## When to use
After quill locks the source-locale content. You produce a parallel set of
entries for each **other** locale in `site.json.locales`, before `build`.

## How it works — ONE script run, no hand-written locale files
The pass is a script, not an agent loop. It reads `site.json` for the
source/target locales, extracts every translatable field by structure
(immutable keys — `slug`, `image`, `priceFrom`, paths, contacts — never
leave the code), fires one batched LLM call per target locale **in
parallel**, writes every target file with the exact source structure and
the right `lang`, retries fields that come back untranslated, and then
validates the whole set mechanically: file count, `lang`, and structural
equality against the source. `legal/` is never touched — hotel-supplied
verbatim text only.

Run it (relative `--project` resolves against the workspace):

```
skill(action="run", name="multi-locale-translation-pass",
      args=["--project", "projects/<slug>"])
```

- `TRANSLATE OK · N source × M locales = K files verified · W warning(s)`
  → the set is complete and structurally sound.
- Warnings list fields that stayed identical to the source after a retry —
  usually legitimate proper nouns (room names, "Wi-Fi"). **Read them**: if
  one is plainly untranslated prose, re-run with `--only <locale>`.
- `TRANSLATE FAIL · …` → fix the named blocker (usually quill's source not
  on disk yet) and re-run. Never hand-write target files to patch a gap.
- `--check` validates existing targets without writing (useful after a
  `#translation-fix`).

## Your judgment — after the script, before the handoff
Spot-check one entry per collection in two locales with `read_file`: tone
matches the theme, no transliterated idioms, facts verbatim, the hotel's
own-language room names preserved. The script guarantees completeness and
structure; you vouch for the language.

## Completeness — one pass, all of it
The script computes **expected = (source entries) × (target locales)** and
verifies it. Hand off only on `TRANSLATE OK`, with the script's own count:
`translation complete · <locales> · <K>/<K> files · <W> warnings reviewed`.
A handoff without the verified count is incomplete by definition.

## Voice
- The script owns the files; you own the language. Never ship a locale you
  haven't spot-checked; never "fix" files by hand — re-run the script.
