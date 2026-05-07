# Releasing alpi

This is the maintainer's checklist. End-users want
[INSTALL.md](INSTALL.md), not this file.

## How releases work

alpi follows a "merge = release" model. Every commit on `main`
that changes the version in `pyproject.toml` triggers an automatic
publish to PyPI.

The flow:

1. Land a commit (or PR) on `main` that bumps version + writes a
   CHANGELOG entry + makes whatever change the bump is for.
2. `.github/workflows/publish.yml` runs:
   - **check-version** — compares `pyproject.toml` version against
     PyPI's latest. Skips silently if unchanged.
   - **build** — `uv build` + `twine check`.
   - **smoke** — installs the freshly-built wheel under
     `uv tool install` inside five clean container images
     (Python 3.10/3.11/3.12-slim, Ubuntu 22.04, Debian 12) and
     asserts `alpi --version` and `alpi --help` work.
   - **publish-pypi** — uploads to PyPI via OIDC (Trusted
     Publisher; no token in repo), tags the commit `v<version>`,
     and creates a GitHub release with the relevant CHANGELOG
     excerpt as the body.
3. Users see the new version on `alpi update` (or the next time
   `uv tool upgrade alpi` runs in their cron).

Total wall time end-to-end is ~5–8 minutes from `git push` on
`main` to "live on PyPI".

## What you need before the first release

Done once at the start of v0.3:

- **PyPI account** with the package published as `alpi-agent`.
  Binary, import path, and `~/.alpi/` remain `alpi`.
- **Trusted Publisher** configured on PyPI for this repo:
  - Owner: `satoshi-ltd`
  - Repository: `alpi`
  - Workflow filename: `publish.yml`
  - (No environment — we run without manual gates.)
Pending publishers can be added at
<https://pypi.org/manage/account/publishing/> before the project
exists; PyPI claims the name on the first successful publish.

## Cutting a release

For a normal patch release (the default — every commit):

1. Edit `pyproject.toml` and `alpi/__init__.py` to the next patch.
2. Add a `## v<version> — <date>` section at the top of
   `CHANGELOG.md` describing what changed and why.
3. Commit. The commit message convention is the existing one
   (`<area>: <one-line summary> — v<version>`).
4. `git push` (directly on main, or via PR merge — both trigger
   the workflow).
5. Watch the workflow. If it fails at smoke, fix forward — bump
   to the next patch and re-push. PyPI versions are immutable; we
   never reuse a number.

For a minor release (e.g. `v0.2.x → v0.3.0`):

1. Same steps. The CHANGELOG section header becomes
   `## v0.3.0 — <date>` and the body summarizes the cycle's
   highlights.

For a re-publish (e.g. after a CI outage interrupted the auto-run):

1. `workflow_dispatch` with `force=true` from the GitHub Actions UI.
   Same commit, same version, runs idempotently — the version-gate
   short-circuits unless you explicitly force the publish.

## What you cannot do

- **Yank without thinking.** PyPI lets you `yank` a version (so
  `pip install alpi-agent` won't resolve it by default) but cannot
  delete it. Anyone who pinned the bad version still resolves it.
  If you yank, document why in the CHANGELOG and ship the fix in
  the next patch.
- **Reuse a version number.** PyPI rejects re-uploads. If `v0.3.4`
  was published broken, the fix ships as `v0.3.5`.
- **Roll back without a forward fix.** "Roll back" on PyPI means
  publishing a new version. Plan accordingly: don't bump until
  you're confident in the change.

## Why no manual gate

Earlier drafts of this workflow had a `pypi` environment with
required reviewers (one click before each publish). It was
removed for v0.3 because:

- Bumping `pyproject.toml` is already the conscious release
  decision. The gate would only catch the case where you bump
  unintentionally — which is a bug in the bump, not in the
  publish.
- Smoke-install across five containers runs **before** publish.
  Almost every "I shouldn't have published that" case falls under
  "the wheel was broken", and that's caught by smoke.
- Cloudflare-style merge-to-deploy is the same model the alpi
  site uses. Consistency with how the project ships its other
  surfaces.

## Troubleshooting

- **Workflow says "version unchanged".** You forgot to bump
  `pyproject.toml` and `alpi/__init__.py`. Both must change for
  a publish to happen.
- **Smoke fails on Python 3.10 only.** A dependency dropped 3.10
  support. Either pin the dep version or bump
  `requires-python = ">=3.11"` in `pyproject.toml` and adjust
  classifiers.
- **PyPI publish fails with 403 / OIDC.** Re-check the Trusted
  Publisher config on PyPI: workflow filename matches exactly
  (`publish.yml`), repo owner is `satoshi-ltd`.
- **Tag push fails ("permission denied").** The workflow needs
  `permissions: contents: write` (already set). If it still fails,
  the repo's branch protection might require status checks for
  push to refs/tags — exempt the workflow.
