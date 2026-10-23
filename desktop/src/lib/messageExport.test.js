import { afterEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import {
  exportArticle,
  exportCss,
  exportFileName,
  exportFooter,
  exportHtml,
  exportMarkdown,
} from "../../../common/messageExport.mjs";
import { PRINT_ROOT_CLASS, clearPrintSheet, downloadMarkdown, mountPrintSheet, printMessage } from "./messageExport.js";

const NOON = new Date(2026, 9, 25, 12).getTime() / 1000;
const CHART = '```chart\n{"type": "line", "title": "Chats per day", "x": ["Mon", "Tue", "Wed"], "series": [{"name": "Chats", "values": [3, 5, 4]}]}\n```';
const MESSAGE = {
  title: "Weekly chat report",
  profile: "pulse",
  server: "casa",
  at: NOON,
  body: `Chats fell **8 %** this week.\n\n${CHART}\n\n| Topic | Chats |\n| --- | --- |\n| Booking | 744 |`,
};

afterEach(() => {
  clearPrintSheet();
  for (const node of document.querySelectorAll(`.${PRINT_ROOT_CLASS}`)) node.remove();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("common/messageExport", () => {
  it("writes the markdown with title, profile, server and body", () => {
    const md = exportMarkdown(MESSAGE);
    expect(md.startsWith("# Weekly chat report\n_@pulse · casa · ")).toBe(true);
    expect(md).toContain("```chart");
    expect(md).toContain("| Booking | 744 |");
  });

  it("names the file after the title, else after the profile and day", () => {
    expect(exportFileName(MESSAGE, "pdf")).toBe("weekly-chat-report.pdf");
    expect(exportFileName({ profile: "pulse", at: NOON }, "md")).toBe("pulse-2026-10-25.md");
    expect(exportFileName({}, "md")).toBe("message.md");
  });

  it("keeps a multi-line title on one line so it cannot add Markdown lines", () => {
    expect(exportMarkdown({ ...MESSAGE, title: "Weekly\n## injected\n\nreport" }).split("\n")[0]).toBe("# Weekly ## injected report");
  });

  it("signs the footer with alpi, the profile and the server", () => {
    expect(exportFooter(MESSAGE)).toMatch(/^alpi · @pulse on casa · /);
    expect(exportFooter({ profile: "pulse" })).toBe("alpi · @pulse");
  });

  it("draws the chart as SVG with the table and the footer, nothing behind the content", () => {
    const html = exportArticle(MESSAGE);
    expect(html).toContain('<figure class="ax-chart">');
    expect(html).toContain("<svg");
    expect(html).toContain("<td>744</td>");
    expect(html).toContain('<tfoot><tr><td><footer class="ax-foot">');
    expect(html).toContain("@pulse on casa");
    expect(html).toContain("<strong>8 %</strong>");
    expect(html).not.toMatch(/position:\s*absolute/);
  });

  it("keeps the numbers of an ordered list, even when it starts past 1 or skips", () => {
    const html = exportArticle({ profile: "pulse", body: "5. fifth step\n6. sixth step\n\n- a\n- b" });
    expect(html).toContain('<ol><li value="5">fifth step</li><li value="6">sixth step</li></ol>');
    expect(html).toContain("<ul><li>a</li><li>b</li></ul>");
    expect(exportArticle({ profile: "pulse", body: "1. one\n3) three" })).toContain('<li value="1">one</li><li value="3">three</li>');
    expect(exportArticle({ profile: "pulse", body: "99999999999999999999999. huge" })).toContain('<li value="2147483647">huge</li>');
  });

  it("escapes message text so a body cannot inject markup", () => {
    const html = exportArticle({ ...MESSAGE, title: "<img src=x onerror=alert(1)>", body: "<script>alert(1)</script>" });
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;script&gt;");
  });

  it("prints in the light palette and keeps charts and rows whole across pages", () => {
    const css = exportCss("#3fb37a");
    expect(css).toContain("background: #ffffff");
    expect(css).toContain("color: #141414");
    expect(css).toContain("--chart-1: #3fb37a");
    expect(css).toMatch(/\.ax-table tr, \.alpi-export figure, \.alpi-export pre \{ break-inside: avoid; \}/);
    expect(css).toContain("display: table-footer-group");
    expect(css).not.toContain("counter(page)");
  });

  it("accepts only a hex accent, so a profile colour cannot break out of the style block", () => {
    const hostile = 'red;}</style><img src=x onerror=alert(1)>';
    expect(exportCss(hostile)).not.toContain("<img");
    expect(exportCss(hostile)).toContain("--chart-1: #141414");
    expect(exportCss("var(--accent)")).toContain("--chart-1: #141414");
    expect(exportHtml(MESSAGE, { accent: hostile })).not.toContain("<img");
    mountPrintSheet(MESSAGE, hostile);
    expect(document.querySelector(`.${PRINT_ROOT_CLASS} img`)).toBeNull();
  });

  it("wraps a standalone document whose title is the file name", () => {
    const doc = exportHtml(MESSAGE, { accent: "#3fb37a" });
    expect(doc.startsWith("<!doctype html>")).toBe(true);
    expect(doc).toContain("<title>Weekly chat report</title>");
    expect(exportHtml({ profile: "pulse", at: NOON })).toContain("<title>pulse-2026-10-25</title>");
  });
});

describe("desktop print sheet", () => {
  it("mounts one print root with only the message, hidden on screen", () => {
    mountPrintSheet(MESSAGE, "#3fb37a");
    mountPrintSheet({ ...MESSAGE, title: "Second" }, null);
    const roots = document.querySelectorAll(`.${PRINT_ROOT_CLASS}`);
    expect(roots).toHaveLength(1);
    expect(roots[0].querySelector("h1").textContent).toBe("Second");
    expect(roots[0].querySelector("style").textContent).toContain(`body > *:not(.${PRINT_ROOT_CLASS}) { display: none !important; }`);
    expect(roots[0].querySelector("style").textContent).toContain(`@media screen { .${PRINT_ROOT_CLASS} { display: none !important; } }`);
  });

  it("prints under the file name and keeps the sheet mounted until printing is over", async () => {
    document.title = "alpi";
    let titleWhilePrinting = null;
    window.print = vi.fn(async () => {
      titleWhilePrinting = document.title;
    });
    await printMessage(MESSAGE, "#3fb37a");
    expect(window.print).toHaveBeenCalledTimes(1);
    expect(titleWhilePrinting).toBe("weekly-chat-report");
    expect(document.title).toBe("weekly-chat-report");
    expect(document.querySelector(`.${PRINT_ROOT_CLASS} .ax-chart svg`)).not.toBeNull();
    window.dispatchEvent(new Event("afterprint"));
    expect(document.querySelector(`.${PRINT_ROOT_CLASS}`)).toBeNull();
    expect(document.title).toBe("alpi");
  });

  it("drops the sheet and restores the title when the print never finishes", () => {
    vi.useFakeTimers();
    document.title = "alpi";
    mountPrintSheet(MESSAGE);
    vi.advanceTimersByTime(10 * 60 * 1000 - 1);
    expect(document.querySelector(`.${PRINT_ROOT_CLASS}`)).not.toBeNull();
    vi.advanceTimersByTime(1);
    expect(document.querySelector(`.${PRINT_ROOT_CLASS}`)).toBeNull();
    expect(document.title).toBe("alpi");
  });

  it("a new export replaces the old sheet and keeps the original title", () => {
    document.title = "alpi";
    mountPrintSheet(MESSAGE);
    mountPrintSheet({ ...MESSAGE, title: "Second" });
    expect(document.querySelectorAll(`.${PRINT_ROOT_CLASS}`)).toHaveLength(1);
    clearPrintSheet();
    expect(document.title).toBe("alpi");
  });

  it("drops the sheet and the title when printing fails", async () => {
    document.title = "alpi";
    window.print = vi.fn(async () => { throw new Error("denied"); });
    await expect(printMessage(MESSAGE)).rejects.toThrow("denied");
    expect(document.querySelector(`.${PRINT_ROOT_CLASS}`)).toBeNull();
    expect(document.title).toBe("alpi");
  });

  it("downloads the markdown to the Downloads folder", async () => {
    invoke.mockResolvedValueOnce({ name: "weekly-chat-report.md" });
    await downloadMarkdown(MESSAGE);
    expect(invoke).toHaveBeenCalledWith("save_text_file", {
      name: "weekly-chat-report.md",
      content: exportMarkdown(MESSAGE),
      dest: "download",
    });
  });
});
