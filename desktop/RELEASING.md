# Releasing the desktop app

The Tauri desktop client ships on its own track, separate from the
alpi (CLI) chain. This document is the canonical recipe for cutting a
new release.

- alpi (CLI) → ``vX.Y.Z`` → PyPI + GitHub release
- desktop app → ``desktop-vX.Y.Z`` → GitHub release only

## What a release does

Pushing a commit to ``main`` that bumps
``desktop/src-tauri/tauri.conf.json``'s ``version`` field triggers
[`.github/workflows/publish-desktop.yml`](../.github/workflows/publish-desktop.yml).
The workflow detects the new version, creates the
``desktop-vX.Y.Z`` tag, and publishes. No manual ``git tag`` step.
This mirrors the alpi CLI's ``publish.yml`` flow.

Two GitHub releases are produced from one run:

1. ``desktop-vX.Y.Z`` — immutable, version-stamped.
2. ``desktop-latest`` — rolling alias the Tauri updater points to.
   Same assets plus stable aliases for the public site. The tag moves
   on every publish so these URLs stay stable:
   ``releases/download/desktop-latest/latest.json``
   ``releases/download/desktop-latest/alpi-latest.dmg``
   ``releases/download/desktop-latest/desktop-release.json``.

Updater artifacts are signed with **minisign** so the installed app
verifies the update before applying it. Pubkey lives in
``tauri.conf.json``; private key + password live in GitHub Actions
secrets. macOS bundles are additionally signed and notarized with an
Apple Developer ID Application certificate.

## Pre-requisites (one-time)

### 1. GitHub Actions secrets

Repo → Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| ``TAURI_SIGNING_PRIVATE_KEY`` | full contents of ``~/.tauri/alpi-updater.key`` |
| ``TAURI_SIGNING_PRIVATE_KEY_PASSWORD`` | password set when the key was generated |
| ``APPLE_CERTIFICATE`` | base64 encoded Developer ID Application ``.p12`` |
| ``APPLE_CERTIFICATE_PASSWORD`` | password set when exporting the ``.p12`` |
| ``APPLE_SIGNING_IDENTITY`` | exact Keychain identity, e.g. ``Developer ID Application: Example Ltd (TEAMID)`` |
| ``APPLE_ID`` | Apple ID email used for notarization |
| ``APPLE_PASSWORD`` | app-specific password for ``APPLE_ID`` |
| ``APPLE_TEAM_ID`` | Apple Developer Team ID |

Verify locally before pushing the secret:

```bash
pbcopy < ~/.tauri/alpi-updater.key
```

The Apple certificate must be exported from Keychain Access as a
password-protected ``.p12`` and encoded with:

```bash
openssl base64 -A -in developer-id-application.p12 -out developer-id-application.p12.base64.txt
```

The ``APPLE_SIGNING_IDENTITY`` value is the exact identity printed by:

```bash
security find-identity -v -p codesigning
```

The pubkey in ``tauri.conf.json`` (``plugins.updater.pubkey``) must
match ``~/.tauri/alpi-updater.key.pub``. They were generated as a
pair — if you ever regenerate one, you regenerate both and update the
``tauri.conf.json`` pubkey field with the new ``.pub`` file content.

### 2. Local key backup

The private key + password are the only thing that lets the installed
app accept future updates. Lose either one and every user has to
reinstall the app fresh.

- Private key file: ``~/.tauri/alpi-updater.key`` — back up to
  encrypted storage (1Password attachment is the recommended path).
- Password: store in 1Password under
  ``tauri-updater-private-key-password``.

If both are lost, regenerate (see *Recovery* below).

## Cutting a release

### 1. Pick the version

Patch (``0.2.0`` → ``0.2.1``) for bug fixes and small improvements.
Minor (``0.2.0`` → ``0.3.0``) for user-visible new features. Major
when something breaks the host-plane contract or the user has to
re-pair.

### 2. Bump the version in three places

```bash
# Edit by hand:
desktop/package.json                  → "version": "X.Y.Z"
desktop/src-tauri/tauri.conf.json     → "version": "X.Y.Z"
desktop/src-tauri/Cargo.toml          → version = "X.Y.Z"
```

After editing ``Cargo.toml``:

```bash
cd desktop/src-tauri && cargo check
```

That refreshes ``Cargo.lock`` to the new version.

### 3. Write the changelog entry

Add a new section at the top of [`desktop/CHANGELOG.md`](CHANGELOG.md):

```
## vX.Y.Z — YYYY-MM-DD — short tagline

Requires alpi ``vA.B.C`` or newer.

Short paragraph framing the release.

- Bullet per concrete change with the file/path and the why.
```

The minimum alpi version is part of the release contract — bump it
only when the desktop genuinely depends on a new daemon verb.

### 4. Smoke test the build locally

```bash
cd desktop
pnpm install --frozen-lockfile
pnpm tauri build --target universal-apple-darwin
```

A successful run produces ``src-tauri/target/universal-apple-darwin/
release/bundle/dmg/Alpi_X.Y.Z_universal.dmg`` plus the signed
``.app.tar.gz`` + ``.app.tar.gz.sig`` the updater needs.

Test the ``.dmg`` on at least one fresh install before tagging —
catches obvious runtime regressions (missing capability, bad
permission, broken IPC) the CI would also catch but locally is
faster to debug.

### 5. Commit and push

```bash
git add desktop/ .github/workflows/publish-desktop.yml
git commit -m "desktop-vX.Y.Z — short tagline

[body matching CHANGELOG.md entry]"
git push origin main
```

The push to main triggers the workflow. The workflow's
``check-version`` job reads ``tauri.conf.json``, derives the tag
``desktop-vX.Y.Z``, and skips if a tag with that name already exists
on origin (so re-pushing the same version is a no-op). On a real
version bump it goes through, creates the tag, and publishes.

To re-publish a version that already shipped (rare — usually only
needed if a release was botched and you want to rebuild from the
same commit), use the workflow's manual dispatch:

- Actions → ``publish-desktop`` → Run workflow → ``force=true``

### 6. Watch the build

`https://github.com/satoshi-ltd/alpi/actions` — pick the
``publish-desktop`` run. Two matrix jobs run in parallel
(macos / ubuntu), then ``promote-latest`` rolls the
``desktop-latest`` tag.

Total wall-clock time: ~10–15 min.

A green run produces:
- ``releases/tag/desktop-vX.Y.Z`` with all platform bundles
- ``releases/tag/desktop-latest`` (rolling) with the same assets
- ``releases/download/desktop-latest/latest.json`` reachable for the
  Tauri updater plugin
- ``releases/download/desktop-latest/alpi-latest.dmg`` reachable for
  the landing page's direct macOS download button
- ``releases/download/desktop-latest/desktop-release.json`` with the
  current desktop version + stable download URLs for any external site

### 7. Verify "Check for updates" works

Open the previously-installed app, Settings → ``check for updates``.
The notification should report the new version and prompt to
download / restart.

## Recovery

### Lost the password

Regenerate the keypair (no users in production = no harm; if there
are users, see *key rotation* below).

```bash
cd desktop
pnpm tauri signer generate -w ~/.tauri/alpi-updater.key.new
mv ~/.tauri/alpi-updater.key      ~/.tauri/alpi-updater.key.old
mv ~/.tauri/alpi-updater.key.pub  ~/.tauri/alpi-updater.key.pub.old
mv ~/.tauri/alpi-updater.key.new      ~/.tauri/alpi-updater.key
mv ~/.tauri/alpi-updater.key.new.pub  ~/.tauri/alpi-updater.key.pub
```

Update ``tauri.conf.json`` ``plugins.updater.pubkey`` with the
contents of the new ``.pub`` file, re-upload the new private key +
password as the two GitHub secrets, then ship a new release.

### Key rotation with users in production

Same flow as *lost the password*, plus:

- Communicate the cutover (new install required) — the new pubkey
  cannot verify the old key's signatures, so every installed app
  refuses the next update.
- Optional belt-and-braces: ship two pubkeys in
  ``plugins.updater.pubkey`` (Tauri 2 supports an array) for one
  release cycle, then drop the old one in the release after.

### Workflow run failed

Common modes:

- ``check-version`` job fails: tag and ``tauri.conf.json`` disagree.
  Fix the file, amend the commit, force-push the tag (only safe
  before the release is live).
- ``secrets present`` fails: a required updater or Apple signing secret
  is missing from GitHub Actions.
- ``build`` matrix job fails on macOS: usually an invalid Apple
  certificate, signing identity, app-specific password, or team ID.
  Developer ID Application builds must be signed and notarized.
- ``promote-latest`` fails: the version-stamped release is fine, only
  the rolling tag move broke. Re-run the job from the Actions UI.

### "Check for updates" returns 404

Means ``releases/download/desktop-latest/latest.json`` does not exist.
Two cases:

- No release has been cut yet → cut one.
- Tag exists but assets are missing → the
  ``promote-latest`` step failed silently (no assets attached to the
  rolling release). Re-run ``promote-latest`` from the Actions UI.

### Landing page shows the wrong desktop version / bad download link

The public site build reads desktop version directly from
``desktop/src-tauri/tauri.conf.json`` and points its macOS button at
``releases/download/desktop-latest/alpi-latest.dmg``. So the release
contract is:

- bump desktop version in the repo
- merge to ``main``
- let ``publish-desktop`` publish ``desktop-latest``
- let ``deploy-site`` rebuild and direct-upload the site from the same
  commit

If the site shows the right version but the button 404s, the release
pipeline is broken. If the button works but the site shows the old
version, the site was not rebuilt from the version-bump commit.
