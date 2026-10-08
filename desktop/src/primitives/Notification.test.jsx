import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NotificationProvider, useNotify } from "./Notification.jsx";

let notifyRef;

function Probe() {
  notifyRef = useNotify();
  return null;
}

function mount() {
  render(
    <NotificationProvider>
      <Probe />
    </NotificationProvider>,
  );
}

describe("error notifications use plain words", () => {
  it("turns a raw daemon slug into a sentence", () => {
    mount();
    act(() => {
      notifyRef({ message: "alp -32029: too-many-connections", variant: "error" });
    });
    expect(
      screen.getByText(
        "This device has too many open connections to the daemon. Wait a few seconds and try again.",
      ),
    ).toBeTruthy();
  });

  it("also maps the legacy danger variant and the danger kind", () => {
    mount();
    act(() => {
      notifyRef({ message: "alp -32029: too-many-connections", variant: "danger" });
      notifyRef({ message: "alp -32029: too-many-requests", kind: "danger" });
    });
    expect(
      screen.getByText(
        "This device has too many open connections to the daemon. Wait a few seconds and try again.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Too many requests at once. Try again in a moment.")).toBeTruthy();
  });

  it("leaves a non-error message untouched", () => {
    mount();
    act(() => {
      notifyRef({ message: "forbidden", variant: "info" });
    });
    expect(screen.getByText("forbidden")).toBeTruthy();
  });

  it("leaves an error it does not know untouched", () => {
    mount();
    act(() => {
      notifyRef({ message: "label required", variant: "error" });
    });
    expect(screen.getByText("label required")).toBeTruthy();
  });
});

describe("toast de-duplication", () => {
  it("drops a repeated plain toast but keeps every toast that carries an action", () => {
    mount();
    act(() => {
      notifyRef({ message: "Saved" });
      notifyRef({ message: "Saved" });
      notifyRef({ message: "Deleted", action: "Undo", onAction: () => {} });
      notifyRef({ message: "Deleted", action: "Undo", onAction: () => {} });
    });
    expect(screen.getAllByText("Saved")).toHaveLength(1);
    expect(screen.getAllByText("Deleted")).toHaveLength(2);
  });
});

describe("the toast stack is capped", () => {
  it("keeps three toasts and retires the oldest for a fourth", () => {
    mount();
    act(() => {
      for (const n of [1, 2, 3, 4]) notifyRef({ message: `Toast ${n}`, action: "Undo", onAction: () => {} });
    });
    expect(screen.queryByText("Toast 1")).toBeNull();
    expect(screen.getByText("Toast 2")).toBeTruthy();
    expect(screen.getByText("Toast 4")).toBeTruthy();
  });

  it("a toast given an id replaces its own text instead of stacking", () => {
    mount();
    act(() => {
      notifyRef({ id: "undo", message: "Deleted “Backup failed”", action: "Undo", onAction: () => {} });
      notifyRef({ id: "undo", message: "Deleted 2 notifications", action: "Undo", onAction: () => {} });
      notifyRef({ id: "undo", message: "Deleted 3 notifications", action: "Undo", onAction: () => {} });
    });
    expect(screen.queryByText("Deleted “Backup failed”")).toBeNull();
    expect(screen.getAllByText("Deleted 3 notifications")).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Undo" })).toHaveLength(1);
  });

  it("a pinned toast spends its full window again on every update", () => {
    vi.useFakeTimers();
    mount();
    act(() => {
      notifyRef({ id: "undo", message: "Deleted “Backup failed”", action: "Undo", onAction: () => {}, duration: 5000 });
    });
    act(() => {
      vi.advanceTimersByTime(4000);
      notifyRef({ id: "undo", message: "Deleted 2 notifications", action: "Undo", onAction: () => {}, duration: 5000 });
    });
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.getByText("Deleted 2 notifications")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(1200);
    });
    expect(screen.queryByText("Deleted 2 notifications")).toBeNull();
    vi.useRealTimers();
  });

  it("hover tells the caller to hold its window and leaving tells it to resume", () => {
    const seen = [];
    mount();
    act(() => {
      notifyRef({
        id: "undo",
        message: "Deleted 2 notifications",
        action: "Undo",
        onAction: () => {},
        onPause: () => seen.push("pause"),
        onResume: () => seen.push("resume"),
      });
    });
    const toast = screen.getByText("Deleted 2 notifications").closest("div");
    act(() => {
      fireEvent.mouseEnter(toast);
      fireEvent.mouseLeave(toast);
    });
    expect(seen).toEqual(["pause", "resume"]);
  });
});

describe("one toast's window is its own", () => {
  it("a later toast does not extend an open toast's window", () => {
    vi.useFakeTimers();
    mount();
    act(() => {
      notifyRef({ message: "Deleted 2 notifications", action: "Undo", onAction: () => {}, duration: 5000 });
    });
    act(() => {
      vi.advanceTimersByTime(4000);
      notifyRef({ message: "Copied" });
    });
    act(() => {
      vi.advanceTimersByTime(1200);
    });
    expect(screen.queryByText("Deleted 2 notifications")).toBeNull();
    expect(screen.getByText("Copied")).toBeTruthy();
    vi.useRealTimers();
  });
});

describe("a pinned toast is never lost while its owner waits on it", () => {
  const undo = (extra = {}) => ({ id: "undo", message: "Deleted 2 notifications", action: "Undo", onAction: () => {}, ...extra });

  it("three later toasts retire an unpinned one, never the pinned Undo", () => {
    mount();
    act(() => {
      notifyRef(undo());
      for (const n of [1, 2, 3, 4]) notifyRef({ message: `Later ${n}`, action: "Open", onAction: () => {} });
    });
    expect(screen.getByText("Deleted 2 notifications")).toBeTruthy();
    expect(screen.queryByText("Later 1")).toBeNull();
    expect(screen.queryByText("Later 2")).toBeNull();
    expect(screen.getByText("Later 4")).toBeTruthy();
  });

  it("a toast removed while hovered still tells its owner to resume", () => {
    const seen = [];
    mount();
    act(() => {
      notifyRef(undo({ onPause: () => seen.push("pause"), onResume: () => seen.push("resume") }));
    });
    act(() => {
      fireEvent.mouseEnter(screen.getByText("Deleted 2 notifications").closest("div"));
    });
    act(() => {
      window.notifyClear("undo");
    });
    expect(screen.queryByText("Deleted 2 notifications")).toBeNull();
    expect(seen).toEqual(["pause", "resume"]);
  });

  it("an update landing during the exit animation keeps the toast", () => {
    vi.useFakeTimers();
    mount();
    act(() => {
      notifyRef(undo({ message: "Deleted “Backup failed”", duration: 5000 }));
    });
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    act(() => {
      notifyRef(undo({ duration: 5000 }));
    });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.getByText("Deleted 2 notifications")).toBeTruthy();
    vi.useRealTimers();
  });

  it("an update while hovered does not restart the countdown", () => {
    vi.useFakeTimers();
    mount();
    act(() => {
      notifyRef(undo({ message: "Deleted “Backup failed”", duration: 5000 }));
    });
    act(() => {
      fireEvent.mouseEnter(screen.getByText("Deleted “Backup failed”").closest("div"));
    });
    act(() => {
      notifyRef(undo({ duration: 5000 }));
      vi.advanceTimersByTime(20000);
    });
    expect(screen.getByText("Deleted 2 notifications")).toBeTruthy();
    vi.useRealTimers();
  });

  it("an Undo clicked twice during the exit leaves no orphan timer to retire a revived toast", () => {
    vi.useFakeTimers();
    mount();
    act(() => {
      notifyRef(undo({ duration: 5000 }));
    });
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    const button = screen.getByRole("button", { name: "Undo" });
    act(() => {
      fireEvent.click(button);
      vi.advanceTimersByTime(50);
      fireEvent.click(button);
    });
    act(() => {
      notifyRef(undo({ duration: 5000 }));
    });
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(screen.getByText("Deleted 2 notifications")).toBeTruthy();
    vi.useRealTimers();
  });

  it("a hovered toast revived by a new delete tells its owner to hold again", () => {
    const seen = [];
    mount();
    const hold = { onPause: () => seen.push("pause"), onResume: () => seen.push("resume") };
    act(() => {
      notifyRef(undo(hold));
    });
    act(() => {
      fireEvent.mouseEnter(screen.getByText("Deleted 2 notifications").closest("div"));
    });
    act(() => {
      notifyRef(undo({ ...hold, message: "Deleted 3 notifications" }));
    });
    expect(seen).toEqual(["pause", "pause"]);
  });
});
