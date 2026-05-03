"""Interactive setup for the Matrix platform (no-E2EE MVP)."""

from __future__ import annotations

import os
from pathlib import Path

from alpi import ui
from alpi.model_selector import _append_env


def run(home: Path) -> None:
    ui.banner(
        ui.crumb("setup", "gateways", "matrix"),
        subtitle="bot + room/sender allowlist",
        home=home,
    )

    current_url = os.environ.get("MATRIX_HOMESERVER_URL", "")
    current_user = os.environ.get("MATRIX_USER_ID", "")
    current_token = os.environ.get("MATRIX_ACCESS_TOKEN", "")
    current_device = os.environ.get("MATRIX_DEVICE_ID", "")
    current_rooms = os.environ.get("MATRIX_ALLOWED_ROOMS", "")
    current_senders = os.environ.get("MATRIX_ALLOWED_SENDERS", "")

    if not current_token:
        ui.dim(
            "You need a Matrix bot account on your homeserver and an\n"
            "access token. ~3 min on your own Synapse / Conduit / Dendrite:\n"
            "\n"
            "  1. Create a bot account (Element → register, or via the\n"
            "     admin API on a closed homeserver).\n"
            "  2. Get an access token:\n"
            "       curl -XPOST -H 'Content-Type: application/json' \\\n"
            "         -d '{\"type\":\"m.login.password\",\"user\":\"alpi-bot\",\\\n"
            "             \"password\":\"…\"}' \\\n"
            "         <homeserver-url>/_matrix/client/r0/login\n"
            "     The reply has ``access_token`` and ``device_id``.\n"
            "  3. From your normal account, create a room and invite\n"
            "     ``@alpi-bot:<server>``. The bot auto-joins on next sync.\n"
            "  4. Copy the room id (Element → room settings → Advanced →\n"
            "     Internal room ID, looks like ``!abc:server``).\n"
            "\n"
            "MVP is no-E2EE: rooms must be unencrypted (Element default\n"
            "for new rooms is encrypted — uncheck before creating).\n"
            "Allowlist is fail-closed; non-allowlisted rooms are ignored.\n"
        )
        ui._console.print("")

    url = ui.text(
        "Homeserver URL (e.g. http://umbrel.local:8008):",
        default=current_url,
    )
    if not url:
        return ui.cancelled()

    user_id = ui.text(
        "Bot user id (e.g. @alpi-bot:server):",
        default=current_user,
    )
    if not user_id:
        return ui.cancelled()

    token = ui.password("Access token:", current=current_token)
    if not token:
        return ui.cancelled()

    device_id = ui.text(
        "Device id (optional, recommended; from the login response):",
        default=current_device,
    )

    rooms_raw = ui.text(
        "Allowed rooms (comma-separated room IDs, e.g. !abc:server):",
        default=current_rooms,
    )
    if not rooms_raw:
        return ui.cancelled()
    rooms = [r.strip() for r in rooms_raw.split(",") if r.strip()]

    senders_raw = ui.text(
        "Allowed senders inside those rooms (optional, leave empty for all members):",
        default=current_senders,
    )
    senders = [s.strip() for s in senders_raw.split(",") if s.strip()]

    env_path = home / ".env"
    _append_env(env_path, "MATRIX_HOMESERVER_URL", url)
    _append_env(env_path, "MATRIX_USER_ID", user_id)
    _append_env(env_path, "MATRIX_ACCESS_TOKEN", token)
    if device_id:
        _append_env(env_path, "MATRIX_DEVICE_ID", device_id)
    _append_env(env_path, "MATRIX_ALLOWED_ROOMS", ",".join(rooms))
    if senders:
        _append_env(env_path, "MATRIX_ALLOWED_SENDERS", ",".join(senders))

    os.environ["MATRIX_HOMESERVER_URL"] = url
    os.environ["MATRIX_USER_ID"] = user_id
    os.environ["MATRIX_ACCESS_TOKEN"] = token
    if device_id:
        os.environ["MATRIX_DEVICE_ID"] = device_id
    os.environ["MATRIX_ALLOWED_ROOMS"] = ",".join(rooms)
    if senders:
        os.environ["MATRIX_ALLOWED_SENDERS"] = ",".join(senders)

    ui.saved_and_wait(env_path)
