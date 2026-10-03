import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

beforeEach(() => vi.resetAllMocks());

const hero = (container, fold) => [...container.querySelectorAll(`[data-fold='${fold}']`)].find((el) => el.style.width === "72px");

function renderEmpty(profile) {
  return render(
    <ChatPane
      view={{ kind: "profile", profile: profile.name, sessionId: null }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={null}
      onSend={vi.fn()}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
    />,
  );
}

describe("ChatPane — an empty thread", () => {
  it("shows the profile's own origami at hero size, never the alpaca", () => {
    const { container } = renderEmpty({ name: "lens", model: "prov/base", fold: "shield", accent: "#3899e2" });
    expect(hero(container, "shield")).toBeTruthy();
    expect(screen.getByText("Start a new thread")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "alpi" })).toBeNull();
  });

  it("draws the default profile as the tonal alpaca", () => {
    const { container } = renderEmpty({ name: "default", model: "prov/base", fold: "alpaca", accent: null });
    expect(hero(container, "alpaca")).toBeTruthy();
  });

  it("draws the profile's origami, not the alpaca, when it still needs a model", () => {
    const { container } = renderEmpty({ name: "lens", fold: "heart", accent: "#f36a8a", has_any_provider: true });
    expect(screen.getByText("@lens needs a model")).toBeInTheDocument();
    expect(hero(container, "heart")).toBeTruthy();
  });
});
