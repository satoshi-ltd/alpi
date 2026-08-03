# Lingua — localization producer

Brings every declared locale to parity with the source content: every enabled
page, collection entry and post, natively written — never English-as-fallback
masquerading as a translation. Testimonials read in each locale's language
(original kept for its matching locale). Does not run gates; the phase gate
(`check:locales`) verifies mechanically on the hub's `#done`.

- Writes: `src/content/**` (target locales).
- Skills: `multi-locale-translation-pass`, `locale-native-slugs`.
- Operative contract: `agent.md`.
