# Tools answer pack

## Answer directly

- Prefer the native tool over shelling out: `read_file` over `terminal cat`,
  `search_workspace`/`search` over `terminal grep`, `write_file` /
  `edit_file` over `terminal sed/perl -i`.
- The workspace is the default root for relative paths, not a sandbox.
  Absolute paths can work, but sensitive paths are denied.
- Tool availability is dynamic: unavailable tools are hidden from the schema;
  `tools.deny` hides and refuses tools per profile.
- Attachments are turn input unless explicitly learned. Output attachments are
  tool-produced files surfaced separately from the final text.
- Use `alpi_knowledge` first for questions about alpi itself.

## Registered tool families

| Family | Tools | Use |
|---|---|---|
| Workspace RAG | `search_workspace`, `index_workspace`, `learn_file` | Semantic search over workspace files and durable learned documents. |
| Session recall | `session_search`, `recall_sessions`, `index_sessions` | Lexical then semantic search over past local chat sessions. |
| Workgroup recall | `workgroup_search`, `index_workgroups` | Semantic search over hub-owned workgroup transcripts. |
| Files | `read_file`, `write_file`, `edit_file`, `search` | Direct filesystem work. |
| Terminal | `terminal` | Shell commands when no native tool fits. Approval + guards apply. |
| Web/browser | `web_search`, `web_fetch`, `web_extract`, `browser`, `research` | Web information; `research` is read-only sub-agent work. |
| Memory | `memory`, `todo` | Durable profile memory and per-turn task tracking. |
| Skills/state | `skill`, `db` | Create/run reusable skills; skill-local SQLite state. |
| Communication | `send_message`, `email`, `schedule`, `peer`, `workgroup`, `ask_user` | Native messages, schedules, ALP peers/workgroups, clarification UI. |
| Media | `read_image`, `tts`, `stt` | Vision, speech synthesis, speech transcription. |
| Delegation | `delegate` | Write-capable focused sub-agent. |
| Self-knowledge | `alpi_knowledge` | Packaged docs about alpi. |

`search` is the registered name from `alpi/tools/search.py`. If conversation
text calls it "search_files" or "workspace grep", still use the schema name the
model actually sees.

## Selection rules

- **Current attached file**: do not index or search the workspace just to read
  an attachment from the current turn. The engine has already supplied it to the
  model. If the user says "learn this", call `learn_file`.
- **Durable company/project docs**: call `learn_file` for explicit learning,
  then use `search_workspace`. Learned docs are copied under
  `<workspace>/.alpi/documents/YYYY/MM/` and indexed.
- **Past chat memory**: use `session_search` first for exact words; if it fails
  or the question is semantic, use `recall_sessions`. Indexing is opt-in via
  `index_sessions`.
- **Workgroup history**: use `workgroup_search` only on hub-owned workgroups.
  It is profile-local, scoped per workgroup, and opt-in via `index_workgroups`.
- **Risky shell command**: use `terminal` only when needed. Caution commands
  may prompt for approval; dangerous commands are refused.
- **Discrete user choice**: use `ask_user` for 2-4 realistic options; do not use
  it as a pre-confirmation for terminal approvals.
- **Reusable procedure**: make or update a skill with `skill`, not ad-hoc files
  under `skills/`.

## Attachments

Inbound per-turn attachments:

- Accepted input types: images (`png/jpeg/webp`), PDF, and text/source files
  (`txt/md/csv/json/yaml/html`, plus common code suffixes).
- The engine validates magic bytes, text-vs-binary, per-file caps, turn caps,
  and count caps before the model sees them.
- Session history stores bytes-free metadata. A best-effort local path may be
  kept for client thumbnails, but it is not durable storage and may be
  unfetchable from another device.
- Remote clients stage files through `host.attachments.stage`; the daemon then
  owns a temporary local path for the turn.

Output attachments (MM.2):

- A scripted tool/skill can return JSON with an absolute `out` path. The engine
  validates the produced file under allowed roots, checks mime/magic/size, and
  stores bytes-free `output_attachments` on the turn.
- Rich clients render images inline and other files as chips; text-only
  surfaces get the shared textual attachment list.
- Do not rely on a markdown `![](/path)` as the source of truth. The attachment
  channel is authoritative.
- Supported output kinds: `image`, `pdf`, `text`, `sheet`, `doc`, `deck`, `file`
  (Office files must be real ZIP-based `xlsx/docx/pptx`).

## Workspace RAG and durable documents

- `index_workspace(path?, glob?, force?, ocr?)` builds/updates the index in
  `<home>/rag/store.sqlite`; it is derived state, not source of truth.
- Text, HTML, PDF, DOCX, EPUB, and images are supported. Scanned PDF/image OCR
  requires `ocr=true`.
- `index_workspace` skips build/dependency/cache dirs and most `.alpi/`, but
  does include `<workspace>/.alpi/documents/` so learned docs survive full
  reindex.
- `learn_file(name?, source_path?, folder?, ocr?)` copies a selected source into
  workspace documents, writes metadata to `manifest.jsonl`, indexes only that
  file, and never overwrites (`-2`, `-3`, ... suffixes).
- If indexing fails, `learn_file` keeps the copied file + manifest and reports
  `indexed:false`.

## Session and workgroup recall

- `session_search` is lexical; `recall_sessions` is semantic. `index_sessions`
  indexes only local `sessions/*.json`, excludes the active session, and never
  injects recall automatically.
- Deleting a session via host sessions deletion purges semantic recall rows;
  reindex orphan-sweeps removed sessions.
- `index_workgroups` indexes decrypted hub-owned transcripts, key-history aware;
  posts that cannot decrypt are skipped. Search is scoped to one workgroup.
- Removing a workgroup purges its workgroup-search rows; reindex orphan-sweeps
  removed workgroups.

## Skills and scripted tools

- Use `skill(action="view")` before editing an existing skill.
- Use `skill(action="add_file")` / `patch` / `set_meta`, not generic write
  tools, so validation and the security scanner run.
- `scripts/run.py` for a scripted skill runs with `sys.executable` from the
  host alpi process. Terminal `python3` resolves from PATH and may differ.
- Skill scripts run with `cwd=<skill_dir>` and receive env such as `ALPI_HOME`,
  `ALPI_SKILL_DIR`, `ALPI_SKILL_NAME`; profile `.env` and active skill env keys
  are scoped through the runtime, not global process mutation.
- Skill secrets live in `<skill>/secrets/` or profile `.env`, never in
  `SKILL.md`, references, scripts, docs, or assets.

## Troubleshooting

- Tool is missing from schema: check `tools.deny`, skill/tool availability,
  missing bins/env/config, or `alpi doctor`.
- Model keeps using a denied tool: executor still refuses denied names even if a
  stale context mentions them.
- Search returns stale/no results: run the matching indexer (`index_workspace`,
  `index_sessions`, `index_workgroups`) and check embedder/root mismatch errors.
- Remote file preview missing: session attachment paths are best-effort; output
  attachment fetch is scoped to profile home/workspace/temp roots.
- Long tool loops on free/local models: default effective step ceiling is higher
  (1000), but an explicit `tools.max_steps_per_turn` always bounds loops.

## Related topics

`architecture` (engine/host contracts) · `skills` (skill lifecycle) ·
`config` (denylist, sandbox, approvals) · `security` (guards/sandbox) ·
`alp` (peer/workgroup tool context)
