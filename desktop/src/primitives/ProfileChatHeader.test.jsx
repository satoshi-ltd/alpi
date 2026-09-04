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
  it("keeps only the model tooltip wide and labels the visible meters", () => {
    const { container } = renderHeader({
      profile: {
        ...profile,
        budget_daily_usd: 10,
        budget_used_usd: 0.26,
      },
    });
    expect(container.querySelectorAll(".ds-tip-wide")).toHaveLength(1);
    expect(container.querySelectorAll(".ds-tip-wide")[0])
      .toHaveTextContent("openrouter/z-ai/glm-5.3-flash");
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
});
