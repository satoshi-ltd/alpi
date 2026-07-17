# Deployment — design (not yet wired)

Today `launched` means **built + QA-passed on disk** — `dist/` is the
artifact, nothing serves it, no git history exists
(`project-lifecycle` says so explicitly). This document is the agreed
design for closing that gap. Nothing below is implemented; when it
lands, each piece arrives as a deterministic script/skill gated by the
pipeline — never as briefing prose.

## The shape

One **git repository per project**, created at launch, with two
long-lived branches mapped to two Cloudflare Pages environments:

```
projects/<slug>/            (already a clean unit: data + assets + template clone)
  .git                      created by the release skill at first launch
  branches:
    dev   → Cloudflare Pages preview   (<slug>-dev.pages.dev)  every commit deploys
    main  → Cloudflare Pages production (hotel's real domain)   every commit deploys
```

- **Why per-project and not one workspace repo:** isolated history per
  client, client handoff stays possible, `archive/` moves don't rewrite
  anyone else's history, and 120 hotels never share one `.git`.
- **Branch flow:** all pipeline and maintenance work commits to `dev`.
  Production is a fast-forward merge `dev → main`, done only after the
  QA gate (initial launch) or the maintenance close (changes). The two
  Cloudflare environments build from the same repo, so dev preview ==
  what production will be.
- **Cloudflare Pages** builds `npm run ship` output (`dist/`);
  `SITE_URL` per environment keeps canonicals honest (preview URL on
  dev, the hotel's domain on main). `dist/` itself stays untracked —
  the repo carries data + assets, the pipeline rebuilds.

## Who commits — no committer profile

A dedicated "committer" agent is the wrong tool: a commit here is not a
judgement call, it is bookkeeping after a gate that already passed.
Adding a 12th profile would add roster cost, another soul to keep
honest, and a second writer of project state next to mira. Instead:

- **pixel** owns the mechanics, as a scripted skill (`project-release`):
  `git init` (first launch) → commit on `dev` → merge to `main` when the
  gate says so → push. Deterministic, same class as `npm run ship` /
  `preflight`. The git identity is a factory bot
  (`web-factory <factory@…>`), configured in the skill, not a persona.
- **mira** stays the gate: the release skill runs only on mira's `#task`
  after QA PASS (initial launch) or at a maintenance close — the same
  places `status.yaml`/`CHANGELOG.md` already get written. The change
  doc's "Commit / deploy reference" field (`maintenance-intake`) becomes
  fillable: one commit hash + the deployed URL.
- Commit messages come from what the pipeline already produces: the
  CHANGELOG line (`v1.0 · launch`, `001-checkin-14 · check-in 14:00`).

## Rollout order

1. **Git layer only** (local, no external deps): `project-release` skill
   creates the repo, commits `dev`, merges `main` at launch. Acceptance
   fixtures assert a repo with both branches exists post-launch. No
   remote, no deploy.
2. **Remote + Cloudflare**: add `git push` + two Pages environments per
   project (API token in the skill's `secrets/`, never in briefings).
   Deploy stays **opt-in per project** (a `deploy:` flag in the brief →
   `status.yaml`), so fixtures and test hotels never publish.
3. **Postcheck**: preflight-style script after each production deploy —
   URL responds, canonical matches `site.json.url`, sitemap reachable.
   A fail is a `#build-fix`-class task, not a silent shrug.

## Open decisions (creator's call before wiring)

- Cloudflare account/zone to use, and whether hotel domains are managed
  there or by the client (affects step 2 only).
- Whether `archive/` projects keep their remote or get archived to a
  bundle on the org box.
