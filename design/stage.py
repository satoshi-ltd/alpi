#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE))

from build import APP_THEMED, FONT_LINK, THEMED  # noqa: E402
from site_stage import SHOTS  # noqa: E402

OUT = REPO / "site" / "assets"
SCALE = 2
BROWSERS = (
    os.environ.get("CHROME", ""),
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    shutil.which("chromium") or "",
    shutil.which("google-chrome") or "",
)


def themed(html):
    for literal, token in THEMED + APP_THEMED:
        html = html.replace(literal, token)
    return html


def document(body, mode):
    return f"""<!doctype html>
<html data-mode="{mode}">
<head>
<meta charset="utf-8">
{FONT_LINK}
<link rel="stylesheet" href="{(REPO / 'desktop/src/styles/tokens.css').as_uri()}">
<link rel="stylesheet" href="{(HERE / 'boards.css').as_uri()}">
<style>html,body{{margin:0;background:transparent;font-family:"Geist",ui-sans-serif,system-ui,sans-serif;color:var(--ink)}}</style>
</head>
<body>{themed(body)}</body>
</html>
"""


SHOOT = r"""
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
const [browser, profile, jobsJson] = process.argv.slice(1);
const jobs = JSON.parse(jobsJson);
const port = 9300 + Math.floor(Math.random() * 600);
const proc = spawn(browser, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
try {
  let target;
  for (let i = 0; i < 100 && !target; i++) {
    await sleep(200);
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch {}
  }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r));
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  for (const job of jobs) {
    await send("Emulation.setDeviceMetricsOverride", { width: job.w, height: job.h, deviceScaleFactor: job.scale, mobile: false });
    await send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
    await send("Page.navigate", { url: job.url });
    await sleep(2500);
    const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: job.w, height: job.h, scale: 1 } });
    writeFileSync(job.out, Buffer.from(shot.result.data, "base64"));
  }
  ws.close();
} finally {
  proc.kill();
}
"""


def main():
    browser = next((b for b in BROWSERS if b and Path(b).exists()), None)
    if not browser:
        sys.exit("no Chromium found; set CHROME to its binary")
    with tempfile.TemporaryDirectory() as tmp:
        jobs = []
        for name, (draw, (w, h)) in SHOTS.items():
            body = draw()
            for mode in ("light", "dark"):
                page = Path(tmp) / f"{name}-{mode}.html"
                page.write_text(document(body, mode))
                jobs.append(dict(url=page.as_uri(), w=w, h=h, scale=SCALE, out=str(OUT / f"stage-{name}-{mode}.png")))
        subprocess.run(["node", "--input-type=module", "-e", SHOOT, browser, f"{tmp}/profile", json.dumps(jobs)], check=True, timeout=180)
        for job in jobs:
            print(Path(job["out"]).relative_to(REPO))


if __name__ == "__main__":
    main()
