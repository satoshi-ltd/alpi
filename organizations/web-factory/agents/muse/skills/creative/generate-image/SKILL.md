---
name: generate-image
description: Generate brand ambience / mood imagery or restore (cleanup/upscale) a low-quality hotel photo via an OpenRouter image model — not for inventing specific inventory photos
category: creative
version: 0.2.0
origin: user
requires_env: [OPENROUTER_API_KEY]
tools: []
output_schema: {"type":"object","properties":{"out":{"type":"string"},"bytes":{"type":"integer"},"model":{"type":"string"},"cost_usd":{"type":"number"}},"required":["out"]}
keywords: ['image', 'photo', 'render', 'raster', 'restore', 'hero', 'ambience', 'openrouter']
created_at: 2026-06-06
---

## When to use

Create on-brand photography from scratch (hero, ambience, mood, texture), or
enhance/reshoot a real hotel photo to look its best. Don't pass fabricated
imagery off as a *specific real room* the hotel never supplied. Logos go through
`make-logo-svg`.

## How to run it — scripted, never the shell

This is a scripted skill. Call it through the runtime, which spawns
`scripts/run.py` with `OPENROUTER_API_KEY` already in its env and returns the
JSON result:

```
skill(action="run", name="generate-image",
      args=["--prompt", "<full prompt>", "--out", "out/<descriptive-name>.jpg", "--aspect", "16:9"])
```

- **Do NOT** run a shell command, `python`, or `python3` yourself, and do NOT
  reference any `factory/tools/...` path. The runtime owns execution; chaining
  the shell yourself is the wrong path (missing key, wrong interpreter, retries).
- `--out`: an absolute path is used as-is. A relative `projects/...` path resolves
  against the **workspace** (project asset); any other relative path resolves
  against your **profile home** (personal chat output). So a workgroup uses
  `projects/<slug>/assets/<name>.png`; a direct chat uses `out/<name>.png` (→
  `~/.alpi/profiles/<you>/out/`). **Not `/tmp/`** — ephemeral, unreferenceable
  next turn, and never a bare filename. `--input` must be **absolute** (the
  attachment or the last real `out`); never guess `/data/attachments`.
- **Enhance / reshoot** (`--input /abs/source.jpg`): improve the real photo —
  upscale, denoise, colour, exposure, and, when asked, **recompose, change the
  angle/framing, relight, declutter**. Name the real elements to keep (furniture,
  art, materials, layout, fixtures) in the prompt so they're preserved. Do NOT
  invent what isn't there — no added/changed amenities or view, no resized or
  different room. If it'd need inventing content, flag it instead.
- **Model.** Always `bytedance-seed/seedream-4.5` (the default) — **don't pass
  `--model`**. It's transformative (striking, professional from-scratch work and
  reshoots); keep elements faithful via the **"must preserve: …"** inventory in the
  prompt, not by switching models. Override only if the maintainer explicitly asks.
- Returns `{"out","bytes","model","cost_usd"}`. The `cost_usd` is added to the
  profile's daily ledger automatically (it counts against `daily_usd`). On failure
  it exits non-zero with the reason — report that as the blocker; don't retry blind.

## Prompt = muse's default style + the subject

Compose the `--prompt` from muse's house photographic style (see agent.md) plus
the specific subject and the brand's 3 feel words — unless the brief or the
user's message specifies a different look, in which case that wins.

## Hard line (see agent.md)

The test is **misrepresentation**, not whether pixels changed. Enhancing or
reshooting the hotel's OWN photo (angle, framing, light, composition) while
preserving its real elements is fine. What's forbidden: inventing what isn't
there — adding/changing amenities or a view, resizing the room, or fabricating a
room with no source photo. When there's no usable source, flag the gap.

## Cost

Each call costs money and is **metered**: the returned `cost_usd` is folded into
the profile's daily ledger (counts against `daily_usd`). **At most 1 raster per
task** unless the hub explicitly asks for more; if more seems needed, hand off a
proposal instead of batch-generating. Don't fill a gallery the hotel can supply.
