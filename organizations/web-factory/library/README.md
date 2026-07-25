# Theme library

The Astro base repository owns the executable design system. This organization
keeps only concise theme guidance for intake and review.

- `starters.md` describes the three theme passports.
- The cloned project's `factory/template-spec.json` is the machine-readable source
  of truth for themes, makeups, tokens, content shapes, scripts and asset slots.
- Runtime CSS, components and visual examples live in the upstream Astro template,
  not in this organization.

Hotel projects may select a theme and supported tokens; they must not fork layout
or CSS locally. A recurring design requirement belongs in the template workgroup.
