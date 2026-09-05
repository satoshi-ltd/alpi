import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import { WorkgroupsField } from "./WorkgroupsField.jsx";

describe("WorkgroupsField", () => {
  it("renders nothing and reports zero when the profile has no workgroups", () => {
    const onCountChange = vi.fn();
    const { container } = render(
      <WorkgroupsField profile={{ name: "mira" }} prefetched={[]} onCountChange={onCountChange} />,
    );
    expect(container).toBeEmptyDOMElement();
    expect(onCountChange).toHaveBeenLastCalledWith(0);
  });

  it("reports the prefetched count and summarises it", () => {
    const onCountChange = vi.fn();
    render(
      <WorkgroupsField
        profile={{ name: "mira" }}
        prefetched={[{ id: "wg_a", name: "site-a", is_hub: true }, { id: "wg_b", name: "site-b", is_hub: false }]}
        onCountChange={onCountChange}
      />,
    );
    expect(onCountChange).toHaveBeenLastCalledWith(2);
    expect(screen.getByText("2 workgroups · 1 hub")).toBeInTheDocument();
  });
});
