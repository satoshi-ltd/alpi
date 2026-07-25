---
name: launch-checklist-walk
description: Perform the final editorial and experience review of a locally built hotel site and issue a test-readiness verdict.
category: meta
version: 1.0.0
origin: user
requires_env: []
tools: [read_file]
keywords: ['qa', 'editorial', 'test-readiness', 'pass-fail']
created_at: 2026-05-29
---

## When to use

After `npm run verify` passes and Mira opens the QA phase. The historical skill
name is retained for registration; this factory does not launch or deploy.

## Audit

- Copy is specific to the hotel, natural in every locale, and contains no demo,
  textual placeholder, TODO or unsupported claim.
- Enabled sections contain meaningful data and disabled sections do not leak
  into navigation.
- Room, offer, booking, club and gallery flows reflect the brief.
- Canonical URLs, `hreflang`, sitemap and robots output cover only canonical
  routes.
- Images resolve and alt text is useful. Missing required media may use the
  template's visibly labelled local placeholder during internal review; report
  every such slot as a warning. `none: true` is only for an intentionally absent
  visual.
- Desktop, tablet and mobile review shows no clipping, overflow, inaccessible
  controls or third-party widget collisions.

Do not fix failures in the QA pass. Name the artifact and return it to the
responsible phase.

## Verdict

End with exactly one line:

- `QA PASS · ready for internal test review`
- `QA FAIL · <blocking issue and owner>`
