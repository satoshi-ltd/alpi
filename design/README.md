# design/

The visual reference for both clients, generated from the code's own values.

- `index.html` · System: tokens from `common/tokens.mjs`, desktop primitives, mobile primitives.
- `desktop.html` · every desktop screen, 1280 wide.
- `mobile.html` · every phone and fold screen.
- `proposals.html` · visual ideas not yet approved, one board each.

Regenerate after a change to a component or token (needs `node` on PATH):

```bash
python3 design/build.py
```

The contract, board format and lifecycle live in [AGENTS.md](AGENTS.md).
