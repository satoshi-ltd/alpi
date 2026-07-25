---
name: scope-bend-decision
description: Decide whether a hotel request fits the clone's authoring surface or requires an upstream template proposal.
category: meta
version: 1.0.0
origin: user
requires_env: []
tools: [read_file, workgroup_post, search]
keywords: ['scope', 'template-fit', 'escalation', 'factory-discipline', 'change-control']
created_at: 2026-05-29
---

# Scope decision

Read `factory/template-spec.json` first.

A project request is in scope when it can be expressed through:

- `src/config/site.json`;
- `src/content/**`, excluding `src/content/config.js`;
- `assets/manifest.yaml` and `assets/source/**`;
- supported tokens, makeups, locales and section switches.

If it needs a new component, schema, route mechanism, runtime integration,
design-system rule or build command, stop project authoring and post a concise
proposal to the Template workgroup. Include the real use case, why existing
handles are insufficient, the smallest reusable change and affected themes.

Do not patch runtime files in one hotel clone. Do not create a new theme for a
single brand preference. Missing client facts remain explicit gaps.
