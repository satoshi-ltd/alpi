import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import Welcome, { ConnectElsewhere, FirstRunHint, firstRunHintSeen, markFirstRunHintSeen } from "./Welcome.jsx";

afterEach(() => {
  cleanup();
  localStorage.clear();
});

const LINK = "alpi://device?url=ws%3A%2F%2F100.1.2.3%3A49200&name=casa&pairing_token=abc";

describe("Welcome", () => {
  it("offers to start an installed alpi that is not running, or to connect elsewhere", () => {
    const onStart = vi.fn();
    render(<Welcome localState="stopped" onStart={onStart} onConnect={vi.fn()} />);
    expect(screen.getByText("alpi is installed but not running")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Start alpi" }));
    expect(onStart).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Connect to another computer" }));
    expect(screen.getByLabelText("alpi:// link")).toBeTruthy();
  });

  it("shows starting, then a failure with the error, the command to run and Retry", () => {
    const onStart = vi.fn();
    const { rerender } = render(<Welcome localState="stopped" phase="starting" onStart={onStart} onConnect={vi.fn()} />);
    expect(screen.getByText("Starting alpi…")).toBeTruthy();
    expect(screen.getByText("Waiting for alpi to answer")).toBeTruthy();
    rerender(<Welcome localState="stopped" phase="failed" error="config.yaml: line 12" onStart={onStart} onConnect={vi.fn()} />);
    expect(screen.getByText("alpi didn't start")).toBeTruthy();
    expect(screen.getByText("config.yaml: line 12")).toBeTruthy();
    expect(screen.getByText("alpi daemon start")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("gives a computer with no alpi two paths: install it here or connect elsewhere", () => {
    const onCheckAgain = vi.fn();
    render(<Welcome localState="absent" onCheckAgain={onCheckAgain} onConnect={vi.fn()} />);
    expect(screen.getByText("Run alpi here")).toBeTruthy();
    expect(screen.getByText("uv tool install alpi-agent")).toBeTruthy();
    expect(screen.getByText("alpi setup")).toBeTruthy();
    expect(screen.getByText("Connect to alpi elsewhere")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(onCheckAgain).toHaveBeenCalledTimes(1);
  });

  it("only offers to connect elsewhere where alpi cannot run", () => {
    render(<Welcome localState="unsupported" onConnect={vi.fn()} />);
    expect(screen.queryByText("Run alpi here")).toBeNull();
    expect(screen.getByText("Connect to alpi elsewhere")).toBeTruthy();
  });
});

describe("ConnectElsewhere", () => {
  const type = (value) => fireEvent.change(screen.getByLabelText("alpi:// link"), { target: { value } });

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
  it("is remembered once dismissed on this machine", () => {
    expect(firstRunHintSeen()).toBe(false);
    const onDismiss = vi.fn(() => markFirstRunHintSeen());
    render(<FirstRunHint onDismiss={onDismiss} />);
    expect(screen.getByText("This is alpi on this computer")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(firstRunHintSeen()).toBe(true);
  });
});
