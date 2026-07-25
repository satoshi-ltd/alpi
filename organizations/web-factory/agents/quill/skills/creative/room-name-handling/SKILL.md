---
name: room-name-handling
description: Preserve the hotel's verified room naming while keeping stable entity slugs and clear localized labels.
category: creative
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, write_file, edit_file]
keywords: ['rooms', 'naming', 'voice', 'i18n', 'slugs']
created_at: 2026-05-29
---

# Room names

Use the hotel's real commercial room names when supplied. If the brief only
provides categories, use clear generic names; do not manufacture poetic names.

Each room has one stable ASCII entity slug shared by every locale. Translate
the visible name only when the hotel does so commercially. Keep capacity,
dimensions, bed type, view, price and features as structured fields, and omit
unknown values rather than guessing.

Validate that every room card and detail entry resolves in every configured
locale and that `npm run check:content` passes for the source locale.
