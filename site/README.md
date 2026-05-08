# alpi.site

The alpi marketing site and documentation. Vanilla HTML/CSS/JS, built by a
single zero-dependency Node script. Deploys to Cloudflare Pages.

## Layout

```
site/
  templates/        source HTML, CSS, runtime JS (authoring)
  assets/           logos and preview images
  scripts/
    markdown.mjs    zero-dep Markdown → HTML renderer
    build.mjs       reads repo docs at HEAD, bakes dist/
  dist/             build output (gitignored, what CF Pages serves)
```

Markdown docs live in the repo root (`README.md`, `QUICKSTART.md`,
`CHANGELOG.md`, `LICENSE`) and in `docs/*.md`. They are rendered at
build time into `dist/docs/<SLUG>.html`, so the site always matches the
commit — no runtime fetch, no GitHub API dependency, no CORS.

## Build

```
node site/scripts/build.mjs
```

No `npm install`. Node ≥ 18. Version string and doc list are derived
from `pyproject.toml` and from `DOCS` in `scripts/build.mjs`.

## Preview locally

```
python3 -m http.server --directory site/dist 8000
```

Then open http://localhost:8000/.

## Cloudflare Pages

Production deploys are GitHub Actions direct uploads. Disable
Cloudflare's automatic production branch deploys; otherwise Cloudflare
can publish a commit before the repo checks and release workflows finish.

GitHub configuration:

- Secret: `CLOUDFLARE_ACCOUNT_ID`
- Secret: `CLOUDFLARE_API_TOKEN` with `Account / Cloudflare Pages / Edit`
- Variable or secret: `CLOUDFLARE_PAGES_PROJECT_NAME`

Workflow: `.github/workflows/deploy-site.yml`

The workflow runs unit tests, integration tests, package build checks,
the site build, and a release-contract gate before the Wrangler direct
upload. The release-contract gate waits until the CLI version from
`pyproject.toml` exists on PyPI, the matching `vX.Y.Z` GitHub release
exists, and the desktop version from `desktop/src-tauri/tauri.conf.json`
exists in the rolling `desktop-latest` GitHub release. That keeps the
landing page from advertising a version or download that did not publish.

Cloudflare Pages build settings are only used if you intentionally run a
Cloudflare-side build:

- Build command: `node site/scripts/build.mjs`
- Build output:  `site/dist`
- Root:          repo root
- Env vars:      none

## Updating docs

Edit the source markdown in `docs/` (or at repo root for README /
QUICKSTART / CHANGELOG / LICENSE), rebuild, deploy. Never edit
`site/dist/` by hand — it is regenerated on every build.

To add a new doc to the site: append an entry to the `DOCS` array in
`scripts/build.mjs` (slug, source path, index, category, sub-title).
Order controls prev/next navigation and the docs index.
