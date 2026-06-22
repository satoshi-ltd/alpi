"""alpi_knowledge tool — read packaged answer packs about alpi itself."""

from __future__ import annotations

from typing import Any

from alpi import knowledge
from alpi.tools.base import Tool, ToolResult


# Per-topic one-liners for the index action. Keys must match alpi.knowledge.TOPICS — tests pin the symmetric diff.
_TOPIC_SUMMARIES: dict[str, str] = {
    "readme": "What alpi is, the project pitch, common commands.",
    "quickstart": "First-time setup walkthrough, install + first message.",
    "install": "Install methods (uv tool, pipx, dev install), update path, uninstall, troubleshooting, supported platforms.",
    "profiles": "Profiles — creating, switching, isolation, identity, keys, memory layout.",
    "skills": "Skills system — frontmatter, security scanner, where credentials live, the skill tool actions.",
    "tools": "Tool selection and contracts — files, terminal, attachments, RAG, recall, outputs, approvals.",
    "models": "Picking a provider, tier guidance for tool-heavy use, local Ollama setup.",
    "alp": "ALP protocol — pinned identity, signed envelopes, peer capabilities, workgroups, group keys, transcript shape, error codes.",
    "architecture": "Internals — code structure, turn loop, gateway, scheduler, MCP, logging, env vars.",
    "config": "Every YAML field, its default, what it controls (TUI theme, sandbox, budget, gateway, schedule).",
    "security": "Approval system, SSRF, prompt-injection, sensitive-path denylist, sandbox.",
    "deployments": "launchd on macOS, systemd on Linux, gateway/schedule daemon shape, keep-alive, log paths.",
    "operations": "Day-2 ops — doctor, diagnostics, log rotation, backup, recovery, upgrade workflow.",
    "organization": "Multi-profile orgs — org.yaml schema, agent.md / workgroup.md frontmatter, peer graph, setup.py modes, persistent workgroups.",
}


class AlpiKnowledge(Tool):
    name = "alpi_knowledge"
    description = (
        "Read packaged documentation about alpi itself. CALL THIS "
        "BEFORE answering any question about alpi — install, profiles, "
        "ALP protocol, tools, skills, models, config, security, gateways, "
        "deployment, day-2 ops, multi-profile organizations. The packaged references are "
        "authoritative; your training predates alpi and will be wrong "
        "about flags, paths, and behaviours.\n"
        "\n"
        "Actions:\n"
        "  index           — list available topics with a one-line summary.\n"
        "  view topic=...  — return the full reference for that topic.\n"
        "\n"
        f"Topics: {', '.join(knowledge.topics())}.\n"
        "\n"
        "Read more than one topic when the question spans them. When "
        "the question isn't covered (stack trace, third-party library, "
        "roadmap, version-specific release notes) say so and only "
        "then fall back to general reasoning or ``web_search``."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["index", "view"],
                "description": "'index' lists topics; 'view' returns one topic's full text.",
            },
            "topic": {
                "type": "string",
                "enum": knowledge.topics(),
                "description": "Required for action='view'.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def run(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        if action == "index":
            return ToolResult(ok=True, output=_render_index())
        if action == "view":
            topic = kwargs.get("topic")
            if not topic:
                return ToolResult(
                    ok=False, output="",
                    error="action='view' requires a topic. Call action='index' to list available topics.",
                )
            try:
                body = knowledge.read(topic)
            except KeyError as e:
                return ToolResult(ok=False, output="", error=str(e))
            return ToolResult(ok=True, output=body)
        return ToolResult(
            ok=False, output="",
            error=f"unknown action: {action!r}. Valid actions: index, view.",
        )


def _render_index() -> str:
    lines = ["Topics available via alpi_knowledge(action='view', topic=<name>):", ""]
    for topic in knowledge.topics():
        summary = _TOPIC_SUMMARIES.get(topic, "")
        lines.append(f"  {topic} — {summary}" if summary else f"  {topic}")
    return "\n".join(lines)


TOOL = AlpiKnowledge


# Headline rule injected into the system prompt so the agent reaches for alpi_knowledge even when it skims tool descriptions.
PROMPT_RULE = (
    "# ALPI SELF-KNOWLEDGE\n"
    "When the user asks about alpi itself (install, profiles, ALP "
    "protocol, tools, skills, config, security, deployment, day-2 ops, "
    "multi-profile organizations / org.yaml / agent.md), "
    "CALL ``alpi_knowledge`` BEFORE answering. The packaged "
    "references are authoritative; your training predates alpi."
)
