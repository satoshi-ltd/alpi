import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _shared():
    script = (
        "const [{ICONS, ICON_ALIASES}, {ICON_ROLES}] = await Promise.all(["
        f"import({json.dumps(str(REPO / 'common' / 'iconPaths.mjs'))}), import({json.dumps(str(REPO / 'common' / 'iconRoles.mjs'))})]);"
        "process.stdout.write(JSON.stringify({icons: Object.keys(ICONS), aliases: ICON_ALIASES, roles: ICON_ROLES}));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_every_icon_role_names_a_shared_icon():
    shared = _shared()
    for role, name in shared["roles"].items():
        assert name in shared["icons"] or shared["aliases"].get(name) in shared["icons"], role


def test_design_boards_draw_each_role_with_its_shared_icon(tmp_path):
    shared = _shared()
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    boards = "".join(p.read_text() for p in (tmp_path / "canvas" / "project").glob("*.dc.html"))
    seen = set()
    for role, icon in re.findall(r'data-icon-role="([^"]+)"[^>]*data-icon="([^"]+)"', boards):
        assert icon == shared["roles"][role], f"design draws {role} with {icon}, the clients use {shared['roles'][role]}"
        seen.add(role)
    assert {"settings", "notifications", "activity"} <= seen

