"""alf's schedule daemon — separate process that fires scheduled jobs.

Use via ``alf schedule start`` / ``stop`` / ``status``. Jobs live in
``~/.alf/schedule/jobs.json`` and are managed by the ``schedule`` tool.

Lifecycle mirrors the gateway's: the daemon only runs when the user
starts it explicitly (``alf schedule start``) or installs it as a
system service (v0.3). No auto-spawn from TUI, gateway, or tools —
adding a job writes to disk but delivery waits for the user to turn
the daemon on, same way adding a Telegram bot in setup doesn't make
the gateway start listening.

``ensure_running(home)`` remains as a helper for the future
``alf schedule install`` flow, but nothing calls it at runtime today.
"""
