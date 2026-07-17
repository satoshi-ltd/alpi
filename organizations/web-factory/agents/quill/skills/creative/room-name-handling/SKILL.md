---
name: room-name-handling
description: Decide how rooms are named across the site — local own-names, generic categories, or hybrid — from the theme + the hotel's naming culture, and land it in the rooms content collection.
category: creative
version: 0.2.0
origin: user
requires_env: []
tools: [read_file, write_file, edit_file]
keywords: ['rooms', 'naming', 'voice', 'i18n', 'own-names']
created_at: 2026-05-29
---

## When to use
After intake captures the room inventory, before quill writes the `rooms`
collection. One naming strategy per project, applied consistently.

## Three strategies
1. **Local own-names** (boutique / small resort) — character-driven names the
   hotel already uses: "la habitación de la esquina", "the garden room".
   Use when <30 rooms, design-led, individually distinguishable.
2. **Generic categories** (budget / business) — "Doble estándar", "Twin",
   "Family room". Use when rooms are fungible / a larger inventory.
3. **Hybrid** — categorical rooms + 1–3 signature named rooms.

| Theme | Default | Override |
|---|---|---|
| boutique | own-names | hotel insists on categories |
| resort | hybrid | small resorts go full own-names |
| business | generic | rare "Director's Suite" exception |
| budget | generic | never override |

## How it lands in the data
Rooms are content entries: `src/content/rooms/<slug>.<lang>.json`, **one file
per room per locale**. The `slug` is stable + ASCII (`corner`, `sea-suite`)
and **identical across locales**. The `name` is the display name in that
locale's file:
- **own-names** → quill writes the source-language name; lingua decides per
  name whether to keep the source language ("la habitación de la esquina"
  may stay in EN) or translate. Proper nouns generally don't translate.
- **generic** → names translate per locale ("Doble estándar" → "Standard
  double"). Avoid marketing-bait ("Deluxe Premium Plus").

The template's RoomCard + room detail + JSON-LD read the collection; the
booking engine maps its own IDs to these names separately (pixel/atlas).

## Voice
- Match the theme: boutique own-names lean evocative, business factual.
- One strategy per project. A proper noun is a proper noun in every locale.
