---
name: analyze-image
description: See an image with an explicit vision model (OpenRouter / Google) and get a text answer — triage supplied hotel photos or inventory a room before a restore. Your reasoning runs on the text base model; this skill is your eyes.
category: creative
version: 0.1.0
origin: user
requires_env: [OPENROUTER_API_KEY]
tools: []
output_schema: {"type":"object","properties":{"answer":{"type":"string"},"model":{"type":"string"},"cost_usd":{"type":"number"}},"required":["answer"]}
keywords: ['image', 'vision', 'analyze', 'triage', 'inventory', 'restore', 'openrouter']
created_at: 2026-06-11
---

## When to use

Your base model is text-only (it reasons; it does not see). This skill is your
eyes — a vision model called on demand:

- **Triage** supplied photos: which are usable, which is hero-grade, which room
  each shows (when filename + brief don't already say).
- **Inventory before a restore** — **MANDATORY**: the brief describes rooms in
  the abstract, not what's in THIS photo. Restore from prose alone and the
  transformative image model invents or drops real elements. So: `analyze-image`
  the source → list its real elements → feed `generate-image --input` a
  `must preserve: …` built from that. Seeing is how you honour *never invent*.

Pure from-scratch work (hero/ambience, no source photo) needs no sight — skip it.

## How to run it — scripted, never the shell

```
skill(action="run", name="analyze-image",
      args=["--image", "/abs/path.jpg", "--question", "List every fixed element: furniture, art, materials, layout, view."])
```

- `--image` absolute path. `--question` focused — "what are the real fixed
  elements?" beats "describe this".
- Returns `{"answer","model","cost_usd"}`; the cost counts against `daily_usd`.
- Metered: call it when seeing changes the outcome (every restore; a triage when
  names don't suffice), not on every file by reflex.
