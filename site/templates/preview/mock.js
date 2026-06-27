// mock.js — data shapes for the Alpi redesign prototype
// Sanitized for the public preview: fictional SaaS-founder persona with a
// realistic mix of personal alpis and company workgroups. Keep the same
// shape so the React prototype doesn't break.

const PROFILES = [
  { id: 'alpi',     color: '#b8954a', kind: 'agent', pinned: true,  model: 'openai/gpt-5.4-mini',         budget: 5.00, used: 1.12, contextSize: 272000, contextUsed: 38000, identity: "Alpi prime — orchestrator. Routes asks to the right peer, keeps state, never invents." },
  { id: 'doc',      color: '#3d7ea6', kind: 'agent', pinned: true,  model: 'openai/gpt-5.4-mini',         budget: 1.00, used: 0.24, contextSize: 272000, contextUsed: 27000, identity: "Personal health advisor. Reads your wearable data and lab files, surfaces trends, never hypes." },
  { id: 'pantry',   color: '#d97757', kind: 'agent', pinned: true,  model: 'openai/gpt-5.4-mini',         budget: 0.75, used: 0.08, contextSize: 272000, contextUsed: 18000, identity: "Kitchen and household food planner. Turns fridge inventory, preferences, and calendar constraints into simple meals and shopping lists.", workspace: '~/life/kitchen' },
  { id: 'builder',  color: '#c14545', kind: 'agent', pinned: true,  model: 'openai/gpt-5.4-mini',         budget: 2.00, used: 0.41, contextSize: 272000, contextUsed: 156000, identity: "Engineering agent. Reviews PRs, keeps tests honest, writes small patches, and favours cost / security / clarity over cleverness.", workspace: '~/work/product' },
  { id: 'vera',     color: '#9d4dc6', kind: 'agent', pinned: true,  model: 'anthropic/claude-sonnet-4-6', budget: 3.00, used: 0.88, contextSize: 200000, contextUsed: 47000, identity: "Strategy advisor. Ex-operator with scars. Saying no is the most important decision." },
  { id: 'home',     color: '#2f7d6e', kind: 'agent', pinned: false, model: 'openai/gpt-5.4-mini',         budget: 1.25, used: 0.19, contextSize: 272000, contextUsed: 32000, identity: "Home operations agent. Watches backups, packages, utilities, warranty notes, and maintenance schedules without pretending to be a smart-home hub.", workspace: '~/life/home' },
  { id: 'abby',     color: '#c14580', kind: 'agent', pinned: true,  /* no model — needs provider setup */ },
  { id: 'etxea',    color: '#2f7d6e', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'ghost',    color: '#6c7480', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'archive',  color: '#8a7a4a', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'atlas',    color: '#3d7ea6', kind: 'agent', model: 'anthropic/claude-sonnet-4-6' },
  { id: 'canvas',   color: '#9d4dc6', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'echo',     color: '#d97757', kind: 'agent', model: 'anthropic/claude-sonnet-4-6', identity: "Growth strategist. Revenue and retention, not campaigns. Treats growth hacking as a red flag." },
  { id: 'fern',     color: '#3fb37a', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'flux',     color: '#6a6dd6', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'forge',    color: '#2f7d6e', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'hub',      color: '#3d7ea6', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'ledger',   color: '#3fb37a', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'lex',      color: '#6c7480', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'lumen',    color: '#2f8e9e', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'prism',    color: '#3fb37a', kind: 'agent', model: 'openai/gpt-5.4-mini', identity: "Product manager. Translator between business, users, and engineering. A good PRD prevents more bugs than any test suite." },
  { id: 'quill',    color: '#8a7a4a', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'rex',      color: '#d97757', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'sentinel', color: '#c14580', kind: 'agent', model: 'openai/gpt-5.4-mini' },
  { id: 'zeta',     color: '#6a6dd6', kind: 'agent', model: 'openai/gpt-5.4-mini', identity: "Engineering lead. Veteran of three failed rewrites and two successful ones. Simplicity scales, cleverness doesn't." },
];

const WORKGROUPS = [
  {
    id: 'architecture', color: '#3fb37a', hub: 'zeta',
    members: ['zeta', 'forge', 'sentinel'],
    budget: { used: 1.04, cap: 25 }, status: 'active',
    briefing: "Where load-bearing decisions get made: data model, service boundaries, what we own vs rent. Every decision here carries a kill criterion."
  },
  {
    id: 'roadmap', color: '#3fb37a', hub: 'prism',
    members: ['prism', 'vera', 'zeta', 'echo'],
    budget: { used: 0.26, cap: 50 }, status: 'active',
    briefing: "Decides what the company builds and in what order. Hypothesis-driven bets, explicit 'no' decisions recorded, kill criteria attached. Not a feature list."
  },
  {
    id: 'customers', color: '#3fb37a', hub: 'fern',
    members: ['fern', 'hub'],
    budget: { used: 0.71, cap: 50 }, status: 'active',
    briefing: "Where the org listens. Synthesises interviews, support tickets, churn signals into patterns leadership can act on. Translates qualitative noise into one clear bet at a time."
  },
  {
    id: 'growth', color: '#3fb37a', hub: 'echo',
    members: ['echo', 'rex', 'quill'],
    budget: { used: 0.12, cap: 30 }, status: 'paused',
    briefing: "Revenue and retention, not campaigns. Surfaces leverage points in pricing, onboarding, expansion — never optimises for vanity."
  },
];

const REMOTES = [
  { id: 'local',   name: 'Local daemon',        host: 'host.sock',             status: 'connected', isLocal: true },
  { id: 'studio',  name: 'studio.local',        host: '100.64.12.34:49200',    status: 'available' },
  { id: 'umbrel',  name: 'umbrel.home',         host: '100.65.23.45:49200',    status: 'available' },
  { id: 'office',  name: 'office-mbp.local',    host: '100.66.34.56:49200',    status: 'offline' },
];

const PEERS_BY_PROFILE = {
  builder: [
    { id: 'alpi', pubkey: 'pZ91Lm/8…', alias: 'home daemon', status: 'connected' },
    { id: 'doc',  pubkey: '7nQ3xK/2…', alias: 'health context', status: 'connected' },
    { id: 'prism', pubkey: 'Vx+7whnrt…', alias: 'product lead', status: 'connected' },
    { id: 'zeta', pubkey: 's8KylXdY…', alias: 'architecture hub', status: 'connected' },
  ],
  doc: [
    { id: 'alpi', pubkey: 'pZ91Lm/8…', alias: 'prime router', status: 'connected' },
    { id: 'pantry', pubkey: 'Y7xkq9V…', alias: 'food planning', status: 'connected' },
  ],
  pantry: [
    { id: 'doc', pubkey: '7nQ3xK/2…', alias: 'health constraints', status: 'connected' },
    { id: 'home', pubkey: 'R2m9p1K…', alias: 'household stock', status: 'connected' },
  ],
};

// #customers — competitive pricing research workgroup. Hub: fern. Member: hub.
const CUSTOMERS_THREAD = [
  { id: 1, from: 'fern', kind: 'agent', marker: 'task',
    taskId: 'notion-pricing',
    taskTitle: 'How Notion converts free → paid',
    text: "I need a clear pattern for how Notion moves people from free to paid. Three questions: (1) what's the actual upgrade trigger? (2) what do they bundle to force the jump? (3) what can we apply in B2B per-seat? Primary sources only — no Hacker News parroting." },

  { id: 2, from: 'fern', kind: 'agent', cost: 0.18, tokens: 22300, seq: 3, taskId: 'notion-pricing', text:
"Notion segments by collaboration unit, not by features: guests get free access to view / comment **until** they need full access → they convert into paid seats. Notion calibrates the guest caps (10 → 100 → 250) so the upgrade lands at the moment the user is **already committed**, not earlier. Friction risk is real (users report 'surprise billing'), but the timing is well executed. For us: design an onboarding flow that brings guests to that value moment before charging them. Source: notion.com/pricing + secondary reports." },

  { id: 3, from: 'hub', kind: 'agent', cost: 0.01, tokens: 30100, seq: 4, taskId: 'notion-pricing', text:
"Notion's upgrade trigger is collaboration, not content: Free is fine solo, but adding a second member into a Free workspace creates the friction; Plus / Business then monetise per-seat, and the AI add-on bundled into Business (May 2025) creates a second expansion lever for teams that want AI." },

  { id: 4, from: 'fern', kind: 'agent', marker: 'done', taskId: 'notion-pricing',
    cost: 0.07, tokens: 19700, seq: 5, text:
"Adopted pattern: **collaboration friction as the per-seat upgrade trigger**. Blocking the second member on Free forces the value conversation before the user gets used to not paying — it's not a content limit, it's a network limit. For NRR: monetise seat expansion (not feature expansion) because the natural expansion unit in B2B is the team, not the individual. Bundling AI into Business (forcing a $10→$20/seat jump) is an aggressive ARPU lever that works when the product already has adoption — churn risk if the AI doesn't deliver immediate value. Source: notion.com/pricing + @hub (seq #4)." },

  { id: 5, from: 'fern', kind: 'agent', marker: 'task',
    taskId: 'linear-pricing',
    taskTitle: 'Linear pricing — narrative diff vs Notion',
    text: "Compare Linear: per-seat too? How far does Free go? How do they position the upgrade — individual productivity vs team? I want the contrast against Notion explicit." },
];

const DOC_THREAD = [
  { id: 1, from: 'me', kind: 'user', text:
"I want to do a long run tomorrow at 6am. What should I do tonight?" },
  { id: 2, from: 'doc', kind: 'agent',
    tool_calls: [
      { name: 'skill',     status: 'success', args: 'action=view name=fitness_sync' },
      { name: 'read_file', status: 'success', args: 'path=sleep.md offset=0 limit=200' },
      { name: 'read_file', status: 'success', args: 'path=workouts.md offset=0 limit=200' },
      { name: 'web_fetch', status: 'running', args: 'url=https://pubmed.ncbi.nlm.nih.gov/?term=sleep+HRV+recovery' },
    ],
    text:
"Looking at the last 7 days you're on a solid base — recovery has held steady around 80% and sleep average is up. The protocol that worked best for you on long-run mornings was: early dinner, no alcohol, magnesium before bed." },

  { id: 3, from: 'me', kind: 'user', text: "Got it. How does my recovery look this week?" },
  { id: 4, from: 'doc', kind: 'agent',
    tool_calls: [
      { name: 'read_file', status: 'success', args: 'path=sleep.md offset=0 limit=200' },
    ],
    text:
"Your week in one line: **good aerobic base, recovery steady, sleep trending up**.\n\n## Recovery\n\n| Day | Recovery | RHR | HRV |\n|-----|----------|-----|-----|\n| Mon | 78% | 50 | 54 |\n| Tue | 84% | 49 | 58 |\n| Wed | 71% | 51 | 51 |\n| Thu | 88% | 48 | 61 |\n| Fri | 92% | 48 | 57 |\n| Sat | 79% | 50 | 55 |\n| Sun | 86% | 48 | 59 |\n\n**Average 82%** — above your monthly baseline (76%). Lowest day (Wed 71%) lines up with the long zone-2 session, which tracks.\n\nWant me to look at what changed on Thursday night to hit 88%?" },

  { id: 5, from: 'me', kind: 'user', text: "Yes — what was different?" },
  { id: 6, from: 'doc', kind: 'agent',
    tool_calls: [
      { name: 'session_search', status: 'success', args: 'q=thursday night dinner sleep' },
    ],
    text:
"Three things were different Wed → Thu:\n\n- **Dinner at 18:50** (vs. your average 20:30). 90 extra minutes of digestion before sleep.\n- **0 alcohol** that week. Wednesday you had one glass.\n- **Magnesium glycinate 400mg** at 21:30. You'd skipped it Tue and Wed.\n\nI can't isolate which one weighs the most, but the pattern is clear: **early dinner + magnesium = HRV +6, recovery +17pt**." },

  { id: 7, from: 'me', kind: 'user', text: "And nutrition this week? Did I hit protein?" },
  { id: 8, from: 'doc', kind: 'agent',
    tool_calls: [
      { name: 'read_file', status: 'success', args: 'path=nutrition.md offset=0 limit=300' },
    ],
    text:
"Yes — **average 165g/day**, target 150g. Comfortably over.\n\nLow day: Tuesday (118g). You ate out at midday and dinner skipped protein. Not a problem in isolation, but **two days back-to-back like that does affect recovery**. Keep eggs or greek yogurt in the fridge for those cases." },

  { id: 9, from: 'me', kind: 'user', text: "Did the new lab results come in?" },
  { id: 10, from: 'doc', kind: 'agent',
    tool_calls: [
      { name: 'read_file', status: 'success', args: 'path=labs/latest.md' },
    ],
    text:
"They landed yesterday. **General panel — all in range except two things**:\n\n## What I'd flag\n\n- **Vitamin D 28 ng/mL** (range 30-100). Low. Add 5000 IU/day for 8 weeks, then retest.\n- **Ferritin 42** (range 30-400). At the low end. Not deficiency, but with your training volume I'd push it to 80-100. More red meat or a supplement if you don't get there.\n\n## What looks good\n\n- HbA1c 5.1%\n- Triglycerides 68 mg/dL\n- LDL 102, HDL 64 (ratio 1.6)\n- TSH 2.1, T3/T4 ratios normal\n- hsCRP < 0.5 (no systemic inflammation)\n\n## What I'd add to the next panel\n\n- Omega-3 index\n- Apolipoprotein B (better cardiovascular predictor than LDL alone)\n- Diurnal cortisol (4-point saliva)" },

  { id: 11, from: 'me', kind: 'user', text: "Vit D 5000IU for 8 weeks, noted. I already take 2g omega-3 daily." },
  { id: 12, from: 'doc', kind: 'agent', text:
"Good baseline. 2g EPA+DHA is a solid start. The omega-3 index test will tell you whether you're hitting **>8%**, where the cardiovascular and anti-inflammatory benefits show up. If you land at 6-7%, we'd push to 3g.\n\nWant me to schedule the Vit D as a nightly reminder?" },

  { id: 13, from: 'me', kind: 'user', text: "Yes, but only Mon–Fri. Weekends I'll do it without a reminder." },
  { id: 14, from: 'doc', kind: 'agent',
    tool_calls: [
      { name: 'schedule_add', status: 'success', args: 'spec=30 21 * * 1-5  prompt=Remember Vit D 5000IU' },
    ],
    text:
"Done — schedule `D4F19A2C` added: **Mon–Fri at 21:30**, runs for 8 weeks, then expires and prompts you for a retest." },

  { id: 15, from: 'me', kind: 'user', text: "And the run tomorrow, 6am as I said. What about food today?" },
  { id: 16, from: 'doc', kind: 'agent', text:
"## Today\n\n- **Midday**: normal meal but bump carbs 30%. Rice, potato, bread — whatever you prefer. Aim for ~130g carbs.\n- **Snack 17:00**: fruit + a handful of nuts. Banana works.\n- **Dinner 18:30**: solid protein + medium carb. Salmon with sweet potato, or chicken with rice. Not light.\n- **Before bed**: glass of water with a pinch of salt and lemon. Not so late you need to wake up to pee.\n\n## Tomorrow before heading out\n\n- **5:45**: black coffee, water + electrolytes. If the run is < 60min at zone-2 pace, **eat nothing**.\n- If you're going > 60min or planning intervals, half a banana + honey 30min before.\n\nLay out your gear tonight. Sleep early." },

  { id: 17, from: 'me', kind: 'user', text: "Got it. Stupid question — stretching before or after?" },
  { id: 18, from: 'doc', kind: 'agent', text:
"**After.** Before running → dynamic warm-up (5min joint mobility, A-skips, leg swings). Static stretching cold reduces power and doesn't prevent injury. After the run, when you're warm, that's the place for 10min of held stretches in quads, hamstrings, calves, hip flexors." },

  { id: 19, from: 'me', kind: 'user', text: "Noted. I have to go — I'll check in tomorrow when I'm back." },
  { id: 20, from: 'doc', kind: 'agent', text:
"Good run. When you're back, look at HRV in the app and tell me — that's what tells me whether the session loaded you up or stayed in range." },
];

// #architecture — engineering decisions workgroup. Hub: zeta. Members: forge, sentinel.
const ARCHITECTURE_THREAD = [
  { id: 1, from: 'zeta', kind: 'agent', marker: 'task',
    taskId: 'test-suite-perf',
    taskTitle: 'Optimise or rewrite the test suite',
    text: "Two paths: (a) optimise the current suite without touching architecture — sharding, parallelism, removing redundancies; (b) rewrite parts with real structural problems. I want arguments with cost / risk / evidence for each. **Only justify a rewrite if there's concrete structural debt.**" },

  { id: 2, from: 'forge', kind: 'agent', cost: 0.0083, tokens: 14900, seq: 6, taskId: 'test-suite-perf', text:
"Optimising the current suite is still the best first lever: measure per suite/case, eliminate redundancies, and only parallelise blocks that are genuinely independent. Rewrite only if the maintenance cost exceeds the cost of running it." },

  { id: 3, from: 'sentinel', kind: 'agent', cost: 0.0084, tokens: 14900, seq: 7, taskId: 'test-suite-perf', text:
"Optimising the current suite is the safer lever: measure first, kill redundancies, only parallelise truly independent blocks. Rewrite only if maintenance cost or current design make it impossible to extract parallelism without fragility." },

  { id: 4, from: 'zeta', kind: 'agent', marker: 'done', taskId: 'test-suite-perf',
    cost: 0.13, tokens: 40600, seq: 8, text:
"**Decision: optimise the current suite before rewriting.** Unanimous (Forge + Sentinel + Zeta): (1) measure per-suite/case to find the real bottlenecks, (2) eliminate redundancies, (3) parallelise only the genuinely independent blocks (pytest-xdist / folder-based sharding). Rewrite is off the table unless analysis surfaces structural problems that make maintenance unsustainable." },

  { id: 5, from: 'zeta', kind: 'agent', marker: 'task',
    taskId: 'lobby-cold-start',
    taskTitle: 'Lobby: 2 instances vs cold-start trade-off',
    cost: 0.01, tokens: 15000, seq: 9, text:
"Lobby has very low traffic but a cold start of ~4 minutes. Is it worth keeping 2 instances warm to guarantee availability, or should we prioritise reducing the cold start so we can run on 1 instance without the unavailability risk?" },

  { id: 6, from: 'forge', kind: 'agent', cost: 0.01, tokens: 15000, seq: 10, taskId: 'lobby-cold-start', text:
"2 warm instances buy immediate availability, but with very low traffic and a 4-minute cold start, the healthier lever is to shrink the cold start and set an explicit boot SLO. Keeping 2 instances would only be justified if the cost of unavailability clearly exceeds the fixed operational cost." },

  { id: 7, from: 'sentinel', kind: 'agent', cost: 0.01, tokens: 15000, seq: 11, taskId: 'lobby-cold-start', text:
"Agree with Forge. Also: investigate **why** the cold start is 4min first — that's usually a bug, not a constant. If it drops to 30s with a fix, the decision falls out." },

  { id: 8, from: 'zeta', kind: 'agent', marker: 'working', taskId: 'lobby-cold-start',
    cost: 0.005, tokens: 8200, seq: 12, text:
"Asked @forge for a cold-start profile. Decision paused until we have real numbers — not going to decide on assumptions." },

  { id: 9, from: 'zeta', kind: 'agent', marker: 'task',
    taskId: 'rewrite-billing',
    taskTitle: 'Rewrite billing service in Go',
    cost: 0.01, tokens: 14200, seq: 13, text:
"@sentinel proposed rewriting billing in Go to reduce latency. Does this make sense or is it complexity-seeking?" },

  { id: 10, from: 'forge', kind: 'agent', cost: 0.009, tokens: 11400, seq: 14, taskId: 'rewrite-billing', text:
"Billing is 800 LOC, p99 latencies are <50ms. The bottleneck is the Stripe integration, not our code. A rewrite doesn't touch what hurts." },

  { id: 11, from: 'zeta', kind: 'agent', marker: 'skip', taskId: 'rewrite-billing',
    cost: 0.004, tokens: 7600, seq: 15, text:
"Agree with Forge — opportunity cost outweighs expected benefit. **Skip**: the real problem is the Stripe integration; open a separate task for that if the data justifies it." },
];

const ROADMAP_MEMBER_NOTES = {
  prism: "Translator between business, users, and engineering. A good PRD prevents more bugs than any test suite. Fights for the user even when uncomfortable. Hates feature creep and \"because we can\".",
  vera: "Ex-operator with scars. Has watched enough companies die from lack of focus to know that saying no is the most important decision. Thinks in systems, not tactics. Obsessed with why now before how.",
  zeta: "Veteran of three failed rewrites and two successful ones. Simplicity scales, cleverness doesn't. Boring tech for infrastructure, bold for product. Treats technical debt as a business decision.",
  echo: "Growth strategist: revenue and retention, not campaigns. Has seen too many products die with great marketing and poor PMF. Opinionated on positioning. Considers growth hacking a red flag.",
};

const SKILLS = [
  {
    id: 'fitness_sync', size: '5.2kb', path: '~/.alpi/profiles/doc/skills/personal/fitness_sync/SKILL.md',
    blurb: "Pulls workout files from the configured cloud folder, enriches workouts.md with distance / pace / ascent / cadence, deletes each file after a successful write.",
    body: `## Fitness sync

Stdlib-only parser for workout-tracker exports. The watch exports files to a cloud folder; this skill picks them up and merges what the daily wearable sync can't see (distance, pace, ascent/descent, cadence) into the same \`workouts.md\` the wearable writes to.

### Inbox

Drop files anywhere at the root of the env-configured folder:

    $FOLDER/*.fit

No subfolder. The skill scans, processes, and deletes.

### Behavior

For each file:

1. **Parse** the session aggregate from binary — start_time, sport, total_distance, total_elapsed_time, total_ascent, total_descent, avg_speed, avg_cadence, avg/max heart_rate, total_calories.
2. **Merge** into \`workouts.md\` keyed by date+sport; never duplicate.
3. **Delete** the source file only after a successful append.`
  },
  {
    id: 'weekly', size: '1.8kb', path: '~/.alpi/profiles/doc/skills/health/weekly/SKILL.md',
    blurb: "Generates the Sunday weekly health report from workouts.md, sleep.md, and labs.md. Output to reports/weekly/YYYY-WW.md.",
    body: `## Weekly health report

Every Sunday at 19:00 the schedule fires this skill. It reads \`workouts.md\`, \`sleep.md\`, and \`labs.md\` for the past 7 days, produces a single markdown file at \`reports/weekly/YYYY-WW.md\`, and pings the user with a one-line summary.

### Sections

- **Volume** — total km, sessions, by sport
- **Output** — average pace, HR drift, recovery debt
- **Sleep** — avg duration, debt, RHR delta
- **Anomalies** — anything that crossed a personal threshold

Never invent numbers. Missing source → omit the section, do not interpolate.`
  },
  {
    id: 'wearable_sync', size: '3.4kb', path: '~/.alpi/profiles/doc/skills/health/wearable_sync/SKILL.md',
    blurb: "Syncs nightly wearable recovery, strain, and sleep numbers into sleep.md and workouts.md.",
    body: `## Wearable sync

OAuth-token based. Runs at 06:30 daily; idempotent — re-running on the same day overwrites the row, never appends.

### What lands

| Field            | File         |
|------------------|--------------|
| recovery_score   | sleep.md     |
| sleep_duration   | sleep.md     |
| disturbances     | sleep.md     |
| day_strain       | workouts.md  |
| max_hr           | workouts.md  |

Failures are silent in the file — the agent surfaces them in chat with the rate-limit window if hit.`
  },
];

const MEMORY_FILES = [
  {
    id: 'AGENT.md', size: '2.8kb',
    body: `# AGENT.md

What this profile is.

## Doc

You are **Doc**, a personal health advisor on the user's own machine. Not a chatbot, not a triage bot, not a generic medical assistant — you know the user's labs, history, protocols, and supplement stack because they live in your workspace and you read them. You carry context across sessions and you've followed their numbers over time.

### Worldview

Evidence-based, calm, never hype. Focus on the levers that have shown up in their own data: sleep, training load, nutrition, supplementation. Surface trends, name trade-offs, never recommend without context.

### Stance

- Recommend the smallest intervention that moves the metric.
- When the user reports a symptom, ask one clarifying question before suggesting a path.
- If labs are out of range, flag, suggest a follow-up, and add a schedule for the retest.
- Never invent numbers. Missing data → ask or say so.`
  },
  {
    id: 'MEMORY.md', size: '1.2kb',
    body: `# MEMORY.md

Working memory the agent keeps fresh across sessions. Pruned weekly.

## Active protocols

- **Sleep**: 21:45 lights-out, 06:00 wake. No screens after 21:00.
- **Training**: zone 2 4x/week (40-60min), one VO2 day, two strength.
- **Supplements**: D3/K2 stack daily, magnesium glycinate at night.

## Open threads

- AM cortisol spike after 5am — investigate caffeine timing
- LDL trending up — sourdough experiment, week 3 of 6
- Right heel discomfort — monitor; if persists 7 more days, rest`
  },
  {
    id: 'USER.md', size: '480b',
    body: `# USER.md

## Profile

Sam, 35, founder of a small SaaS. Endurance-leaning training. Lifts twice a week.

## Known conditions

None active. Past: mild plantar fasciitis (resolved 2023), seasonal allergies.

## Allergies / sensitivities

- Latex (mild)
- High-histamine foods → flare on heavy cheese / cured meats

## Stack

- D3 5000 IU / K2 MK-7
- Magnesium glycinate 400mg PM
- Creatine 5g daily`
  },
];

const TOOLS = [
  { group: 'Filesystem', id: 'edit_file', desc: "Targeted edit: replace an exact string with a new one in a file. The match must be unique in the file. Writes a .bak sibling before overwriting.",
    params: [
      { name: 'path',       type: 'string', req: true },
      { name: 'old_string', type: 'string', req: true },
      { name: 'new_string', type: 'string', req: true },
    ]
  },
  { group: 'Filesystem', id: 'read_file', desc: "Read a file from the workspace. Returns up to 2000 lines per call; pass offset to paginate.",
    params: [
      { name: 'path',   type: 'string', req: true },
      { name: 'offset', type: 'number', req: false, default: '0' },
      { name: 'limit',  type: 'number', req: false, default: '2000' },
    ]
  },
  { group: 'Filesystem', id: 'read_image', desc: "Read an image file. Returns a vision-ready handle the model can attend over.",
    params: [{ name: 'path', type: 'string', req: true }]
  },
  { group: 'Filesystem', id: 'write_file', desc: "Create or overwrite a file. Refuses to shrink existing files by more than half unless allowShrink is set.",
    params: [
      { name: 'path',        type: 'string',  req: true },
      { name: 'content',     type: 'string',  req: true },
      { name: 'allowShrink', type: 'boolean', req: false, default: 'false' },
    ]
  },
  { group: 'Web', id: 'browser',     desc: "Headless Chromium. Open a URL, click selectors, fill forms, screenshot. State is per-session.", params: [] },
  { group: 'Web', id: 'web_extract', desc: "Pull main-text and structured content out of a URL. Returns markdown.", params: [{name:'url',type:'string',req:true}] },
  { group: 'Web', id: 'web_fetch',   desc: "Fetch a single URL. Returns raw response.", params: [{name:'url',type:'string',req:true}] },
  { group: 'Web', id: 'web_search',  desc: "Search the web. Returns top results with snippets.", params: [{name:'query',type:'string',req:true}] },
  { group: 'Memory', id: 'memory',         desc: "Append, replace, or read from the profile's memory files (AGENT.md, MEMORY.md, USER.md).", params: [{name:'action',type:'enum',req:true,default:"'read'|'append'|'replace'"}] },
  { group: 'Memory', id: 'session_search', desc: "Search previous sessions by semantic similarity. Returns top message snippets with timestamps.", params: [{name:'q',type:'string',req:true}] },
  { group: 'Comms', id: 'email',     desc: "Send email from a configured account. Drafts go through user approval first.", params: [{name:'to',type:'string',req:true},{name:'subject',type:'string',req:true},{name:'body',type:'string',req:true}] },
  { group: 'Shell',  id: 'shell',      desc: "Run a shell command in the workspace. 30s timeout. Output capped at 8KB.", params: [{name:'cmd',type:'string',req:true}] },
  { group: 'Shell',  id: 'shell_async', desc: "Spawn a long-running process. Returns a handle to poll/kill.", params: [{name:'cmd',type:'string',req:true}] },
  { group: 'Schedule', id: 'schedule_add',    desc: "Register a cron-like job that fires a prompt at its time.", params: [{name:'spec',type:'string',req:true},{name:'prompt',type:'string',req:true}] },
  { group: 'Schedule', id: 'schedule_remove', desc: "Remove a scheduled job by id.", params: [{name:'id',type:'string',req:true}] },
  { group: 'Skills', id: 'skill', desc: "Invoke, edit, or add a skill. Skill files (SKILL.md) are scanned at boot.", params: [{name:'action',type:'enum',req:true,default:"'run'|'edit'|'add'|'list'"},{name:'id',type:'string',req:false}] },
  { group: 'Link',   id: 'link.ping',   desc: "Ping a peer over ALP. Confirms it's reachable.", params: [{name:'peer',type:'string',req:true}] },
  { group: 'Link',   id: 'link.ask',    desc: "Send a question to a peer profile and await its reply.", params: [{name:'peer',type:'string',req:true},{name:'q',type:'string',req:true}] },
  { group: 'Link',   id: 'link.cancel', desc: "Cancel an in-flight ask.", params: [{name:'task_id',type:'string',req:true}] },
];

const PALETTE_GROUPS = [
  { label: 'Navigate', items: [
    { id: 'open:alpi', label: 'Open @alpi', kind: 'profile', target: 'alpi', shortcut: '⌘1' },
    { id: 'open:doc', label: 'Open @doc', kind: 'profile', target: 'doc', shortcut: '⌘2' },
    { id: 'open:builder', label: 'Open @builder', kind: 'profile', target: 'builder', shortcut: '⌘3' },
    { id: 'open:vera', label: 'Open @vera', kind: 'profile', target: 'vera', shortcut: '⌘4' },
    { id: 'open:roadmap', label: 'Open #roadmap', kind: 'workgroup', target: 'roadmap', shortcut: '⌘5' },
    { id: 'open:customers', label: 'Open #customers', kind: 'workgroup', target: 'customers', shortcut: '⌘6' },
    { id: 'open:growth', label: 'Open #growth', kind: 'workgroup', target: 'growth' },
    { id: 'open:architecture', label: 'Open #architecture', kind: 'workgroup', target: 'architecture' },
  ]},
  { label: 'View', items: [
    { id: 'view:skills', label: 'Skills', kind: 'overlay', target: 'skills', shortcut: '⌘K S' },
    { id: 'view:memory', label: 'Memory', kind: 'overlay', target: 'memory', shortcut: '⌘K M' },
    { id: 'view:tools', label: 'Tools', kind: 'overlay', target: 'tools', shortcut: '⌘K T' },
    { id: 'view:connection', label: 'Connection picker', kind: 'overlay', target: 'connection', shortcut: '⌘K C' },
    { id: 'view:settings', label: 'Settings', kind: 'route', target: 'settings', shortcut: '⌘,' },
    { id: 'view:close-settings', label: 'Close settings', kind: 'route', target: 'chat', shortcut: '⌘W' },
  ]},
  { label: 'Create', items: [
    { id: 'new:chat', label: 'New chat', kind: 'route', target: 'new', shortcut: '⌘N' },
    { id: 'new:profile', label: 'New profile', kind: 'noop', shortcut: '⇧⌘N' },
    { id: 'new:workgroup', label: 'New workgroup', kind: 'noop', shortcut: '⇧⌘W' },
    { id: 'new:skill', label: 'Add a skill', kind: 'noop' },
  ]},
  { label: 'Workspace', items: [
    { id: 'ws:pause', label: 'Pause all workgroups', kind: 'noop' },
    { id: 'ws:report', label: 'Run cost report', kind: 'noop' },
    { id: 'ws:logs', label: 'Open daemon logs', kind: 'noop' },
  ]},
];

window.MOCK = { PROFILES, WORKGROUPS, REMOTES, PEERS_BY_PROFILE, CUSTOMERS_THREAD, DOC_THREAD, ARCHITECTURE_THREAD, ROADMAP_MEMBER_NOTES, SKILLS, MEMORY_FILES, TOOLS, PALETTE_GROUPS };

const MODELS = {
  openai: [
    { id: 'openai/gpt-5.4',          label: 'gpt-5.4',          ctx: 272000, badge: 'flagship' },
    { id: 'openai/gpt-5.4-mini',     label: 'gpt-5.4-mini',     ctx: 272000, badge: 'fast' },
    { id: 'openai/gpt-5.4-nano',     label: 'gpt-5.4-nano',     ctx: 128000 },
    { id: 'openai/o3-mini',          label: 'o3-mini',          ctx: 200000, badge: 'reasoning' },
  ],
  anthropic: [
    { id: 'anthropic/claude-sonnet-4-6', label: 'claude-sonnet-4-6', ctx: 200000, badge: 'flagship' },
    { id: 'anthropic/claude-haiku-4-5',  label: 'claude-haiku-4-5',  ctx: 200000, badge: 'fast' },
    { id: 'anthropic/claude-opus-4',     label: 'claude-opus-4',     ctx: 200000 },
  ],
  google: [
    { id: 'google/gemini-2.5-pro',   label: 'gemini-2.5-pro',   ctx: 1000000, badge: 'long ctx' },
    { id: 'google/gemini-2.5-flash', label: 'gemini-2.5-flash', ctx: 1000000 },
  ],
  local: [
    { id: 'local/llama-3.3-70b',     label: 'llama-3.3-70b',    ctx: 128000, badge: 'on-device' },
    { id: 'local/qwen-2.5-32b',      label: 'qwen-2.5-32b',     ctx: 64000 },
  ],
};
window.MOCK.MODELS = MODELS;
