import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import WorkgroupChatHeader from "./WorkgroupChatHeader.jsx";

const workgroup = { id: "wg_1", name: "ops" };

describe("WorkgroupChatHeader flag", () => {
  it("flags the name while a pipeline waits on the user or failed, never while running or paused", () => {
    const { container, rerender } = render(<WorkgroupChatHeader workgroup={workgroup} hubName="mira" mark={{ state: "needs", phase: [1, 3], owner: "yuri" }} />);
    expect(container.querySelector(".title-row [data-flag]")).toHaveAttribute("data-flag", "warning");
    rerender(<WorkgroupChatHeader workgroup={workgroup} hubName="mira" mark={{ state: "failed" }} />);
    expect(container.querySelector("[data-flag]")).toHaveAttribute("data-flag", "danger");
    rerender(<WorkgroupChatHeader workgroup={workgroup} hubName="mira" mark={{ state: "running", phase: [1, 3] }} />);
    expect(container.querySelector("[data-flag]")).toBeNull();
    rerender(<WorkgroupChatHeader workgroup={workgroup} hubName="mira" paused mark={{ state: "needs" }} />);
    expect(container.querySelector("[data-flag]")).toBeNull();
  });
});
