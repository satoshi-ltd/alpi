import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import ProfileChatHeader from "./ProfileChatHeader.jsx";

const profile = { name: "smith", accent: "#008F11", model: "openrouter/z-ai/glm-5.3-flash" };

function renderHeader(extra = {}) {
  return render(
    <ProfileChatHeader
      profile={profile}
      sessionData={{ last_ctx_tokens: 20000 }}
      model={profile.model}
      contextWindow={200000}
      sessionsButton={null}
      {...extra}
    />,
  );
}

describe("ProfileChatHeader context meter", () => {
  it("writes the full model id in the menu, reachable without hovering, and labels the visible meters", () => {
    const { container } = renderHeader({
      profile: {
        ...profile,
        budget_daily_usd: 10,
        budget_used_usd: 0.26,
      },
    });
    expect(container.querySelectorAll(".ds-tip-wide")).toHaveLength(0);
    expect(container.querySelector("[role='dialog'] [data-model-id]")).toHaveTextContent("openrouter/z-ai/glm-5.3-flash");
    expect(container.textContent).toContain("Context window");
    expect(container.textContent).toContain("Daily budget");
  });

  it("shows the persisted session tokens when no turn is live", () => {
    const { container } = renderHeader();
    expect(container.textContent).toContain("20K/200K");
  });

  it("prefers the live streaming value over the stale session snapshot", () => {
    const { container } = renderHeader({ liveCtxTokens: 155000 });
    expect(container.textContent).toContain("155K/200K");
    expect(container.textContent).not.toContain("20K/200K");
  });

  it("falls back to the session snapshot while the live turn has no usage yet", () => {
    const { container } = renderHeader({ liveCtxTokens: null });
    expect(container.textContent).toContain("20K/200K");
  });

  it.each([
    [{ budget_daily_usd: 1, budget_used_usd: 0.85 }, 0, "Daily budget 85% used"],
    [{ budget_daily_usd: 1, budget_used_usd: 1.2 }, 0, "Daily budget 100% used"],
    [{}, 170000, "Context 85% full"],
  ])("flags the name when a meter passes 80 %%", (extra, ctx, label) => {
    const { container } = renderHeader({ profile: { ...profile, ...extra }, liveCtxTokens: ctx || null });
    const flag = container.querySelector(".title-row [data-flag]");
    expect(flag).toHaveAttribute("aria-label", label);
    expect(flag).toHaveAttribute("role", "img");
  });

  it("draws no flag under 80 % or while paused", () => {
    const { container, rerender } = renderHeader({ profile: { ...profile, budget_daily_usd: 1, budget_used_usd: 0.5 } });
    expect(container.querySelector("[data-flag]")).toBeNull();
    rerender(<ProfileChatHeader profile={{ ...profile, budget_daily_usd: 1, budget_used_usd: 0.95 }} paused sessionsButton={null} />);
    expect(container.querySelector("[data-flag]")).toBeNull();
  });
});
