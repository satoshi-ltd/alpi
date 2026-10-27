import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ALPACA_FOLD, foldPolygons } from "../../../common/folds.mjs";
import { LINK_SOURCE_ROWS } from "../../../common/onboarding.mjs";
import Welcome, { ConnectElsewhere, FirstRunHint, firstRunHintSeen, markFirstRunHintSeen } from "./Welcome.jsx";

afterEach(() => {
  cleanup();
  localStorage.clear();
});

const LINK = "alpi://device?url=ws%3A%2F%2F100.1.2.3%3A49200&name=casa&pairing_token=abc";

const primaries = () => screen.queryAllByRole("button").filter((b) => b.dataset.variant === "primary");
const names = () => screen.queryAllByRole("button").filter((b) => b.textContent).map((b) => b.textContent);
const before = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
const LOG = Array.from({ length: 30 }, (_, i) => `line ${i + 1}`).join("\n");

const STATES = [
  ["absent", { localState: "absent" }],
  ["stopped", { localState: "stopped" }],
  ["unsupported", { localState: "unsupported" }],
  ["installing", { localState: "absent", phase: "installing" }],
  ["starting", { localState: "stopped", phase: "starting" }],
  ["failed", { localState: "stopped", phase: "failed", error: "boom" }],
  ["install-failed", { localState: "absent", phase: "install-failed", error: "Download failed" }],
  ["install-failed without a reason", { localState: "absent", phase: "install-failed" }],
];

describe("Welcome", () => {
  it.each(STATES)("%s: one h1, one drag strip, at most one primary, never two", (_, props) => {
    const { container } = render(<Welcome {...props} onConnect={vi.fn()} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.queryAllByRole("heading", { level: 2 })).toHaveLength(0);
    expect(container.querySelectorAll("[data-drag]")).toHaveLength(1);
    expect(container.querySelector("[data-drag]").parentElement.firstElementChild).toBe(container.querySelector("[data-drag]"));
    expect(primaries().length).toBeLessThanOrEqual(1);
  });

  it.each(STATES.filter(([, props]) => !["installing", "starting"].includes(props.phase) && props.localState !== "unsupported"))("%s: the primary is first in its row and holds focus on mount", (_, props) => {
    render(<Welcome {...props} onConnect={vi.fn()} />);
    const [primary] = primaries();
    expect(primary).toBeTruthy();
    expect(document.activeElement).toBe(primary);
    const row = primary.parentElement;
    expect(row.firstElementChild).toBe(primary);
    expect(primary.className).toMatch(/\blg\b|_lg_/);
    for (const other of row.querySelectorAll("button:not([data-variant=primary])")) {
      expect(other.dataset.variant).toBe("ghost");
      expect(other.className).toMatch(/_lg_/);
    }
  });

  it("absent: the sentence that says what alpi is, then Install and start as the only primary, Check again and the ghost", () => {
    const onCheckAgain = vi.fn();
    const onInstall = vi.fn();
    render(<Welcome localState="absent" onInstall={onInstall} onCheckAgain={onCheckAgain} onConnect={vi.fn()} />);
    const title = screen.getByRole("heading", { name: "Set up alpi" });
    const sentence = screen.getByText("alpi runs your agents on this computer. Installing it needs an internet connection.");
    expect(before(title, sentence)).toBe(true);
    expect(before(sentence, screen.getByRole("button", { name: "Install and start alpi" }))).toBe(true);
    expect(names()).toEqual(["Install and start alpi", "Check again", "Connect to another computer"]);
    expect(primaries().map((b) => b.textContent)).toEqual(["Install and start alpi"]);
    expect(screen.queryByText("Run alpi here")).toBeNull();
    expect(screen.queryByText("Connect to alpi elsewhere")).toBeNull();
    expect(screen.queryByLabelText("alpi:// link")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    expect(onInstall).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(onCheckAgain).toHaveBeenCalledTimes(1);
  });

  it("draws the alpaca as the 72 px tonal Fold with its ink, not its box, on the column edge", () => {
    const { container } = render(<Welcome localState="absent" onConnect={vi.fn()} />);
    const mark = container.querySelector("[data-fold='alpaca']").parentElement;
    expect(mark.style.width).toBe("72px");
    expect(mark.style.height).toBe("72px");
    const [top, , bottom, left] = mark.style.margin.split(" ").map(parseFloat);
    const polygons = foldPolygons(ALPACA_FOLD, "#808080", 72).flatMap((f) => f.points);
    expect(-left).toBeCloseTo(Math.min(...polygons.map(([x]) => x)) * 0.72, 1);
    expect(-top).toBeCloseTo(Math.min(...polygons.map(([, y]) => y)) * 0.72, 1);
    expect(-bottom).toBeCloseTo((100 - Math.max(...polygons.map(([, y]) => y))) * 0.72, 1);
  });

  it("stopped: Start alpi is the primary, with the ghost after it", () => {
    const onStart = vi.fn();
    render(<Welcome localState="stopped" onStart={onStart} onConnect={vi.fn()} />);
    expect(screen.getByText("alpi is installed but not running")).toBeTruthy();
    expect(screen.getByText("Start it here, or connect to an alpi that runs somewhere else.")).toBeTruthy();
    expect(names()).toEqual(["Start alpi", "Connect to another computer"]);
    fireEvent.click(screen.getByRole("button", { name: "Start alpi" }));
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("opens the link form in place of the actions and Back returns to the state it came from", () => {
    render(<Welcome localState="stopped" onStart={vi.fn()} onConnect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Connect to another computer" }));
    expect(screen.getByRole("heading", { name: "Connect to alpi" })).toBeTruthy();
    expect(screen.getByText("Paste the link made on the computer that runs it.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Start alpi" })).toBeNull();
    expect(document.activeElement).toBe(screen.getByLabelText("alpi:// link"));
    expect(names()).toEqual(["Connect", "Back"]);
    expect(primaries().map((b) => b.textContent)).toEqual(["Connect"]);
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "alpi is installed but not running" })).toBeTruthy();
    expect(screen.queryByLabelText("alpi:// link")).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Start alpi" }));
  });

  it("unsupported: the link form alone under the reason, with no Back", () => {
    render(<Welcome localState="unsupported" onConnect={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Connect to alpi" })).toBeTruthy();
    expect(screen.getByText("alpi does not run on this system yet, so connect to one that runs elsewhere.")).toBeTruthy();
    expect(screen.queryByText("Run alpi here")).toBeNull();
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
    expect(names()).toEqual(["Connect"]);
    expect(document.activeElement).toBe(screen.getByLabelText("alpi:// link"));
  });

  it("installing and starting show the BusyMark and the ladder, announce politely and offer no button", async () => {
    const { container, rerender } = render(<Welcome localState="absent" phase="installing" />);
    const section = container.querySelector("section");
    expect(section.getAttribute("aria-live")).toBe("polite");
    expect(section.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByRole("heading", { name: "Installing alpi…" })).toBeTruthy();
    expect(screen.getByText("Downloading uv, Python and alpi. This can take a few minutes. Keep this window open.")).toBeTruthy();
    expect(await screen.findByRole("status", { hidden: true })).toBeTruthy();
    expect(container.querySelector("[role=status] svg").getAttribute("width")).toBe("72");
    expect(screen.getByText("Installing alpi and its runtime").closest("li").dataset.state).toBe("now");
    expect(screen.getByText("Start alpi").closest("li").dataset.state).toBe("todo");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    rerender(<Welcome localState="stopped" phase="starting" />);
    expect(container.querySelector("section").getAttribute("aria-live")).toBe("polite");
    expect(screen.getByRole("heading", { name: "Starting alpi…" })).toBeTruthy();
    expect(screen.getByRole("status", { hidden: true })).toBeTruthy();
    expect(screen.getByText("Start requested").closest("li").dataset.state).toBe("done");
    expect(screen.getByText("Waiting for alpi to answer").closest("li").dataset.state).toBe("now");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("puts the BusyMark exactly where the Fold stands, so the title never moves between states", async () => {
    const { container, rerender } = render(<Welcome localState="stopped" phase="failed" error="boom" onStart={vi.fn()} />);
    const fold = container.querySelector("[data-fold]").parentElement;
    rerender(<Welcome localState="stopped" phase="starting" />);
    await screen.findByRole("status", { hidden: true });
    const busy = container.querySelector("[role=status]").parentElement;
    expect(busy.style.margin).toBe(fold.style.margin);
    expect(busy.style.width).toBe(fold.style.width);
    expect(busy.style.height).toBe(fold.style.height);
  });

  it("shows starting, then a failure with the error, the command to run and Retry as the primary", () => {
    const onStart = vi.fn();
    const { rerender } = render(<Welcome localState="stopped" phase="starting" onStart={onStart} onConnect={vi.fn()} />);
    rerender(<Welcome localState="stopped" phase="failed" error="config.yaml: line 12" onStart={onStart} onConnect={vi.fn()} />);
    const title = screen.getByRole("heading", { name: "alpi didn't start" });
    const log = screen.getByText("config.yaml: line 12");
    const sentence = screen.getByText("Start it from a terminal to see what it says:");
    const command = screen.getByText("alpi daemon start");
    const retry = screen.getByRole("button", { name: "Retry" });
    expect([title, log, sentence, command, retry].every((el, i, all) => i === 0 || before(all[i - 1], el))).toBe(true);
    expect(log.tagName).toBe("PRE");
    expect(screen.getByRole("button", { name: "Copy alpi daemon start" })).toBeTruthy();
    expect(primaries()).toEqual([retry]);
    expect(names().filter((n) => n !== "")).toEqual(["Retry", "Connect to another computer"]);
    fireEvent.click(retry);
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("announces a busy state once: the section is the only live region and the BusyMark is hidden from it", async () => {
    const { container } = render(<Welcome localState="absent" phase="installing" />);
    await screen.findByRole("status", { hidden: true });
    expect(container.querySelectorAll("[aria-live]")).toHaveLength(1);
    const mark = container.querySelector("[role=status]").closest("[aria-hidden]");
    expect(mark.getAttribute("aria-hidden")).toBe("true");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("makes the failure log a focusable, named region so a keyboard can scroll it", () => {
    render(<Welcome localState="stopped" phase="failed" error={LOG} onStart={vi.fn()} />);
    const log = screen.getByRole("region", { name: "Error output" });
    expect(log.tagName).toBe("PRE");
    expect(log.tabIndex).toBe(0);
  });

  it("focuses the primary on mount without scrolling the column", () => {
    const focus = vi.spyOn(HTMLElement.prototype, "focus");
    render(<Welcome localState="stopped" onStart={vi.fn()} />);
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Start alpi" }));
    focus.mockRestore();
  });

  it("keeps the pasted link when the screen changes under an open form", () => {
    const { rerender } = render(<Welcome localState="stopped" onStart={vi.fn()} onConnect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Connect to another computer" }));
    fireEvent.change(screen.getByLabelText("alpi:// link"), { target: { value: LINK } });
    rerender(<Welcome localState="stopped" phase="starting" onConnect={vi.fn()} />);
    rerender(<Welcome localState="stopped" phase="failed" error="boom" onStart={vi.fn()} onConnect={vi.fn()} />);
    expect(screen.getByLabelText("alpi:// link").value).toBe(LINK);
  });

  it("scrolls the failure log to its tail", () => {
    const heights = vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockReturnValue(480);
    render(<Welcome localState="stopped" phase="failed" error={LOG} onStart={vi.fn()} />);
    expect(screen.getByText(/line 30/).scrollTop).toBe(480);
    heights.mockRestore();
  });

  it("install-failed: Retry is the primary and runs the install; with no reason it says what to check", () => {
    const onInstall = vi.fn();
    const { rerender } = render(<Welcome localState="absent" phase="install-failed" error="Download failed" onInstall={onInstall} onConnect={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "alpi couldn't be installed" })).toBeTruthy();
    expect(screen.getByText("Download failed").tagName).toBe("PRE");
    expect(screen.queryByText("alpi daemon start")).toBeNull();
    expect(primaries().map((b) => b.textContent)).toEqual(["Retry"]);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onInstall).toHaveBeenCalledOnce();
    rerender(<Welcome localState="absent" phase="install-failed" onInstall={onInstall} onConnect={vi.fn()} />);
    expect(screen.getByText("Check your internet connection, then try again.")).toBeTruthy();
  });

  it("says an installation failure once", () => {
    const { rerender } = render(<Welcome localState="absent" phase="install-failed" error="Could not download uv. Check your internet connection and try again." onInstall={vi.fn()} />);
    expect(screen.queryByText("Check your internet connection, then try again.")).toBeNull();
    rerender(<Welcome localState="absent" phase="install-failed" onInstall={vi.fn()} />);
    expect(screen.getByText("Check your internet connection, then try again.")).toBeTruthy();
  });

  it("draws every action of every state at one size and never two primaries", () => {
    for (const [, props] of STATES) {
      const { unmount } = render(<Welcome {...props} onConnect={vi.fn()} />);
      const sized = screen.queryAllByRole("button").filter((b) => b.textContent);
      expect(sized.every((b) => /_lg_/.test(b.className))).toBe(true);
      expect(primaries().length).toBeLessThanOrEqual(1);
      unmount();
    }
  });

  it("keeps the old stacked layout out of the sheet", () => {
    const css = readFileSync(join(import.meta.dirname, "Welcome.module.css"), "utf8");
    expect(css).not.toMatch(/ghostFlush|\.choice|\.choices/);
  });
});

describe("ConnectElsewhere", () => {
  const type = (value) => fireEvent.change(screen.getByLabelText("alpi:// link"), { target: { value } });

  it("labels the field visibly and lists the two sources as label and path", () => {
    render(<ConnectElsewhere onConnect={vi.fn()} />);
    const field = screen.getByLabelText("alpi:// link");
    expect(field.tagName).toBe("INPUT");
    expect(document.querySelector(`label[for="${field.id}"]`).textContent).toBe("alpi:// link");
    const items = [...document.querySelectorAll("ul > li")];
    expect(items.map((li) => [li.children[0].textContent, li.children[1].textContent])).toEqual(LINK_SOURCE_ROWS.map(({ label, path }) => [label, path]));
    expect(items).toHaveLength(2);
    expect(items.every((li) => li.children[1].classList.contains("mono"))).toBe(true);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("dims Connect until a link is pasted and has no Back without onBack", () => {
    render(<ConnectElsewhere onConnect={vi.fn()} />);
    const connect = screen.getByRole("button", { name: "Connect" });
    expect(connect.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("alpi:// link"), { target: { value: LINK } });
    expect(connect.disabled).toBe(false);
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
  });

  it("puts Back beside the primary in one action row", () => {
    const onBack = vi.fn();
    render(<ConnectElsewhere onConnect={vi.fn()} onBack={onBack} />);
    const connect = screen.getByRole("button", { name: "Connect" });
    const back = screen.getByRole("button", { name: "Back" });
    expect(connect.parentElement).toBe(back.parentElement);
    expect(connect.nextElementSibling).toBe(back);
    expect(back.dataset.variant).toBe("ghost");
    fireEvent.click(back);
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("replaces the sources by the ladder while connecting and keeps the action slot", async () => {
    render(<ConnectElsewhere onConnect={() => new Promise(() => {})} onBack={vi.fn()} />);
    type(LINK);
    const slot = screen.getByRole("button", { name: "Connect" }).parentElement;
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Connect" })); });
    expect(document.querySelector("ul > li > .mono")).toBeNull();
    expect(document.querySelectorAll("ol > li")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Connect" }).parentElement).toBe(slot);
    expect(screen.getByRole("button", { name: "Connect" }).disabled).toBe(true);
  });

  it("shows one failure line between the ladder and the actions, with Try again in the Connect slot", async () => {
    render(<ConnectElsewhere onConnect={async () => { throw new Error("connection closed before response"); }} onBack={vi.fn()} />);
    type(LINK);
    const connect = screen.getByRole("button", { name: "Connect" });
    await act(async () => { fireEvent.click(connect); });
    const alert = screen.getByRole("alert");
    expect(alert.children[0].textContent).toBe("Can't reach casa");
    expect(alert.children[1].textContent).toBeTruthy();
    const ladder = document.querySelector("ol");
    const actions = connect.parentElement;
    expect(ladder.compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(alert.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBe(connect);
    expect(connect.nextElementSibling.textContent).toBe("Back");
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("names a link that is not an alpi link at the first step", async () => {
    render(<ConnectElsewhere onConnect={vi.fn()} />);
    type("https://example.com");
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Connect" })); });
    expect(screen.getByText("That is not an alpi link")).toBeTruthy();
  });

  it("keeps the link and names the host when it cannot be reached", async () => {
    const onConnect = vi.fn(async () => { throw new Error("connection closed before response"); });
    render(<ConnectElsewhere onConnect={onConnect} />);
    type(LINK);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Connect" })); });
    expect(onConnect).toHaveBeenCalledWith(LINK);
    expect(screen.getByText("Can't reach casa")).toBeTruthy();
    expect(screen.getByText("Link read").closest("li").dataset.state).toBe("done");
    expect(screen.getByText("Reaching casa").closest("li").dataset.state).toBe("fail");
    expect(screen.getByLabelText("alpi:// link").value).toBe(LINK);
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("clears a used link and asks for a new one", async () => {
    render(<ConnectElsewhere onConnect={async () => { throw new Error("alp -32011: pairing-used — pairing code already used"); }} />);
    type(LINK);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Connect" })); });
    expect(screen.getByText("This link was already used or has expired")).toBeTruthy();
    expect(screen.getByText("Signing in").closest("li").dataset.state).toBe("fail");
    expect(screen.getByLabelText("alpi:// link").value).toBe("");
  });

  it("marks every step done once the host accepts the link", async () => {
    render(<ConnectElsewhere onConnect={async () => ({ name: "casa" })} />);
    type(LINK);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Connect" })); });
    expect([...document.querySelectorAll("li[data-state]")].map((li) => li.dataset.state)).toEqual(["done", "done", "done"]);
  });
});

describe("FirstRunHint", () => {
  it("is one Mono line with the fact and where a phone gets its link, and no button", () => {
    const { container } = render(<FirstRunHint />);
    const line = container.querySelector("p .mono");
    expect(line.textContent).toBe("This is alpi on this computer · To use it from a phone: Settings → Connections");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("is remembered once marked on this machine", () => {
    expect(firstRunHintSeen()).toBe(false);
    markFirstRunHintSeen();
    expect(firstRunHintSeen()).toBe(true);
  });
});
