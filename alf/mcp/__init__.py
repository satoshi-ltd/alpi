"""MCP (Model Context Protocol) client subsystem.

Spawns user-configured MCP servers as subprocesses, discovers their
tools, and registers them into alf's tool registry with a ``<server>:``
prefix so they coexist with native tools.

Zero MCPs ship with alf by default. The user declares them in
``~/.alf/config.yaml`` under ``mcp.servers.*`` (via ``alf setup``);
secrets go in ``.env`` referenced as ``env:VAR_NAME``. Alf spawns
what you configured, nothing else — matches the same "user in
control" principle the rest of the codebase follows.
"""
