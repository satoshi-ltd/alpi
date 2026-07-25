---
name: hotel-voice-tone
description: Write complete source-locale hotel content for the template without inventing facts or bypassing its content schemas.
category: creative
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, search, write_file, edit_file]
keywords: ['content', 'voice', 'tone', 'copywriting', 'data', 'i18n-source']
created_at: 2026-05-29
---

# Hotel voice and tone

Read the brief, intake, site config, content schemas and clone-local template
spec. Write source-locale entries under `src/content/**`; never edit
`src/content/config.js` or runtime files.

Use concrete hotel evidence, a consistent voice and useful booking context.
Keep headlines expressive but clear, body copy scannable and operational facts
literal. Do not invent amenities, history, sustainability claims, policies,
awards, reviews, prices or availability.

Every enabled section must contain meaningful content. Disable genuinely absent
sections in configuration. Leave human/legal gaps explicit. Finish with
`npm run check:content` and hand off the source locale plus any unresolved warnings.
