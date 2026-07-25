# Web Factory operating memory

- The organization is in test mode; it does not deploy or publish.
- Every hotel has a stable slug and an independent clone under `projects/<slug>`.
- The upstream base repository is `satoshi-ltd/alpi-mirai-web-factory`.
- Kivara remains the upstream demo while the three themes mature.
- New clones are neutralized with `npm run site:init` through the bootstrap tool.
- Client media belongs in `assets/source/`; optimized derivatives are generated.
- Missing required media defaults to a descriptive local placeholder. Image
  generation is opt-in and requires explicit client or hub authorization.
- Themes are `essential`, `signature`, and `immersive`.
- Explicit client choice wins; an agent may decide from evidence; otherwise use
  `signature`.
- The cloned template specification and schemas are authoritative.
- Project agents edit content/config/assets only. Framework changes go upstream.
- No invented hotel facts, facilities, room imagery, certifications, or legal
  claims.
- A project is complete for this phase only when `npm run verify` passes and Lens
  records QA PASS.
