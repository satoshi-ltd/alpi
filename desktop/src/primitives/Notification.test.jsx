import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
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
