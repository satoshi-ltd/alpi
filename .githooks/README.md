# Git hooks

Versioned hooks for this repo. Enable per clone:

```bash
git config core.hooksPath .githooks
```

## `pre-push`

Regenerates `CHANGELOG.md` before pushing. If the file was stale, it
rewrites it in the working tree and blocks the push — commit the
refresh, then push again. Never amends or commits on your behalf.

Runs `uv run alpi release notes`, so `uv` must be on PATH. If it
isn't the hook skips silently; never blocks on a dev-env hiccup.
