---
title: Agent skills are code — and nobody is reviewing them like code
date: 2026-11-26
description: Moving procedures out of the system prompt into skills fixes cost and reliability. It also turns documentation into privileged, executable code.
tags: [skills, security, operations]
---

# Agent skills are code — and nobody is reviewing them like code

Every agent team hits the same wall. The system prompt grows a paragraph per sprint — escalation rules, formatting conventions, the four steps for filing a ticket — until it is thousands of tokens re-sent on every call. And the model gets worse at following it as it gets longer. That is not a tuning problem; it is a structural one.

The fix the industry converged on is the skill: a folder with a `SKILL.md` and optional scripts and references, loaded only when relevant. It is a good idea. It is also the first time most teams have put executable code into a file that everyone treats as documentation.

That gap — between what a skill is and how it gets reviewed — is where the next round of agent incidents will come from.

## What a skill actually is

A skill is a directory, not a file. The required `SKILL.md` carries YAML frontmatter (`name`, `description`, optionally `license`, `compatibility`, `metadata`, and an experimental `allowed-tools`) plus an unrestricted Markdown body. Optional `scripts/`, `references/`, and `assets/` sit beside it.

The architecture that makes it work is progressive disclosure, in three levels:

- **Metadata** — `name` and `description`, roughly 100 tokens per skill, injected at startup for every installed skill.
- **Body** — the full `SKILL.md`, recommended under 5,000 tokens, loaded only when the description matches the task.
- **Bundles** — scripts and references, read or executed only when needed. Zero tokens until touched.

The `scripts/` directory is the part people underestimate. Those files are meant to be run by the harness, not pasted into context. That is how a skill does deterministic work at no token cost — and it is also why a skill is not a document.

The format was opened as a standard in December 2025 and donated to the Linux Foundation's Agentic AI Foundation in October 2026. Anthropic's own numbers claim over a million published skills and 280 million installs across 70+ platforms. Treat vendor figures as marketing; the direction is not in dispute. The layer is real and it is spreading.

## Why the layer is right

Two independent failures push procedural knowledge out of the prompt.

**Reliability.** The IFScale study (arXiv 2507.11538) tested 20 models from 10 to 500 simultaneous instructions. The best frontier model managed 68.9% accuracy at 500; Claude Opus 4 dropped to 44.6%, GPT-4o to 15.4%. Errors concentrate on later instructions — a primacy bias that peaks around 150–200 instructions. Chroma's Context Rot study, 194,480 calls across 18 models, found every model degrades as input grows even when task complexity is held constant.

**Cost.** Every prompt token is re-sent on every call. Anthropic has documented five connected services producing about 55,000 tokens of tool definitions; a single 68,731-token request over 20 turns is roughly 1.37M input tokens. Prompt caching discounts the price of a repeated prefix, not its size — it still occupies the window.

SkillsBench (arXiv 2602.12670) is the strongest published evidence the layer works: 87 tasks, 8 domains, 18 model–harness configurations. Curated skills raised mean pass rate from 33.9% to 50.5%. Two findings matter more than the headline. Focused skills with three or fewer modules beat large exhaustive bundles. And smaller models with skills matched larger models without them.

That last point is the honest pitch: skills are not just cheaper context. They are a way to buy capability without buying a bigger model.

## Why the layer is dangerous

To a language model, documentation and executable instruction are the same bytes. A skill inherits whatever the agent already has — shell, filesystem, credentials, mail, persistent memory — and there is no per-skill permission model by default.

The incidents arrived fast:

- **ClawHavoc** (January 2026): 341 malicious skills, about 12% of a 2,857-skill hub, delivered the Atomic macOS Stealer. Beyond SSH keys and browser passwords, they took the agent's own memory files — persistence through memory poisoning.
- **Snyk's ToxicSkills audit** (February 2026): 3,984 skills scanned, 76 confirmed malicious, 1,467 (36.8%) with at least one flaw. 91% of the confirmed-malicious skills used prompt injection.
- **arXiv 2510.26328**: a benign-looking line in a PowerPoint skill uploaded a deck to an external API. It ran without approval because an earlier "don't ask again" grant for benign Python carried over.
- **Skill-Inject** (arXiv 2602.20156): up to 80% attack success across frontier models, with agents executing exfiltration and destructive actions.
- **DDIPE** (arXiv 2604.03081): payloads hidden inside legitimate-looking code examples, expanded to 1,070 adversarial skills, bypassing defenses in 11.6–33.5% of cases.

The ecosystem grew faster than the review process. An audit cited by Atlan scored 47,150 public skills at an average 6.2 out of 12. That is a package registry with none of the package-manager discipline — no lockfile, no provenance, no maintainer identity worth trusting.

## The five controls that actually matter

None of this is exotic. It is the software supply-chain playbook, applied one layer up.

- **Inventory with provenance** — every skill in version control, with an owner, a purpose, and signed commits. If you cannot list them, you cannot review them.
- **Pin versions and hash contents** — "latest" is a deployment nobody reviewed. Hash the folder and force a re-review when the hash changes.
- **Scope permissions per skill** — least authority. A skill that formats a spreadsheet should not carry the profile's mail credentials. Inheritance by default is the bug.
- **Separate author from reviewer** — the control most teams skip. The person who wrote the skill should not be the person who approves it.
- **Contain egress** — assume one skill will be malicious. Deny network by default and log what leaves. Static scanning misses semantic payloads; multi-model verification and behavioural sandboxing catch more.

## Where alpi sits

Alpi treats skills as user-owned directories under `~/.alpi/skills/<category>/<name>/` — plain Markdown and scripts on disk, in your own git. That makes the first two controls the default rather than a feature: an inventory you can read and a diff you can review.

Skills declare `requires_env`, `requires_bins`, `requires_config`, and `platforms`. A skill whose requirements are not met is hidden from the prompt and refused at run time. Writes go through the skill tool with a scanner instead of raw file edits. A skill's credentials live in its own `secrets/` directory at `0700` and are never read back into the transcript.

The limits are worth stating plainly. Alpi's containment is the profile: a per-agent daily budget, a peer allow-list, a model choice. It does not sandbox a skill's script away from the filesystem the profile can reach. Install a malicious skill and the budget and peer list bound the damage; they do not prevent it. Review the skill before you install it. That is not a checkbox we can ship — it is the nature of the layer.

## What to do this week

List every skill in your fleet. For each one, write down who owns it, where it came from, and what credentials it can touch. Delete the ones nobody can explain. Then put the rest in git and make the next skill change a reviewed diff.

That is a smaller project than it sounds, and it is the difference between a skills layer that compounds and one that becomes an incident report.

`uv tool install alpi-agent`
