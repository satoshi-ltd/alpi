import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { eyebrow } from "../../../common/tokens.mjs";

const SRC = join(import.meta.dirname, "..");
const ACRONYMS = new Set(["URL", "TCP", "WSS", "MCP", "IMAP", "SMTP", "KEY", "VALUE", "API", "ALP", "SSH", "USD", "PDF"]);

function sources(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.jsx$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

export function pieces(children) {
  const direct = children.replace(/\{[^{}]*(\{[^{}]*\}[^{}]*)*\}/g, "\u0000").split("\u0000").map((s) => s.trim()).filter(Boolean);
  const quoted = [...children.matchAll(/(["'`])((?:(?!\1)[^\\\n]|\\.)*)\1/g)].map((m) => m[2].replace(/\$\{[^}]*\}/g, "").trim()).filter(Boolean);
  return [...direct, ...quoted];
}

export function fault(children) {
  if (/\.toUpperCase\(\)/.test(children)) return "is upper-cased in code";
  for (const piece of pieces(children)) {
    if (/^[a-z]/.test(piece)) return `"${piece}" starts in lower case`;
    const shout = piece.split(/[^A-Za-z]+/).find((word) => /^[A-Z]{3,}$/.test(word) && !ACRONYMS.has(word));
    if (shout) return `"${piece}" shouts ${shout}`;
    if (/\b[A-Z]{2,} [A-Z]{2,}\b/.test(piece)) return `"${piece}" shouts`;
  }
  return null;
}

function labels() {
  const found = [];
  for (const path of sources(SRC)) {
    const text = readFileSync(path, "utf8");
    const where = path.slice(SRC.length + 1);
    for (const match of text.matchAll(/<Eyebrow\b[^>]*>([\s\S]*?)<\/Eyebrow>/g)) found.push({ children: match[1], where });
    for (const match of text.matchAll(/className=(?:"eyebrow\b[^"]*"|\{`eyebrow\b[^`]*`\})[^>]*>([\s\S]*?)<\//g)) found.push({ children: match[1], where });
  }
  return found;
}

describe("eyebrow labels", () => {
  it("are written in sentence case, the case the design system gives them", () => {
    expect(eyebrow.case).toBe("sentence");
    const all = labels();
    expect(all.length).toBeGreaterThan(60);
    const wrong = all.map(({ children, where }) => ({ where, fault: fault(children) })).filter((label) => label.fault);
    expect(wrong).toEqual([]);
  });

  it.each([
    ["NAME"], ["HUB"], ["ARGS"], ["PORT"], ["SAVED RECIPES"], ["API KEY"], ["providers"], ["tools{count}"], ['{k.toUpperCase()}'],
    ['{signed ? "USING CHATGPT PLAN" : "Use your plan"}'], ['{locked ? "No host yet." : "where alpi runs"}'], ["MEMBERS — PEERS OF @{name}"],
  ])("the guard refuses %s", (children) => expect(fault(children)).not.toBeNull());

  it.each([
    ["Name"], ["URL"], ["TCP port"], ["Public WSS route"], ["Token ID"], ["API key"], ["Env (KEY=VALUE per line)"],
    ["Linked peers · {peers.length}"], ['{sentenceCase(k)}{required ? "" : " (optional)"}'], ["{group.label}"], ["Members — peers of @{name}"],
  ])("the guard accepts %s", (children) => expect(fault(children)).toBeNull());
});
