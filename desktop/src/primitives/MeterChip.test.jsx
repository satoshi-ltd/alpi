import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import MeterChip from "./MeterChip.jsx";
import EmptyState from "./EmptyState.jsx";

describe("MeterChip", () => {
  it("draws no bar and a dash below one percent", () => {
    const { container } = render(<MeterChip value="0K" pct={0.004} />);
    expect(container.querySelector("[role='progressbar']")).toBeNull();
    expect(container.querySelector(".pct")).toHaveTextContent("—");
  });

  it("draws the bar and the rounded percent from one percent up", () => {
    const { container } = render(<MeterChip value="9K" pct={0.02} />);
    expect(container.querySelector("[role='progressbar']")).not.toBeNull();
    expect(container.querySelector(".pct")).toHaveTextContent("2%");
  });

  it("fills with the colour it is given and leaves the default to the stylesheet's accent", () => {
    const { container, rerender } = render(<MeterChip value="9K" pct={0.5} color="#3899e2" />);
    const fill = () => container.querySelector("[role='progressbar'] > i");
    expect(fill().style.background).toBe("rgb(56, 153, 226)");
    rerender(<MeterChip value="9K" pct={0.5} />);
    expect(fill().style.background).toBe("");
  });
});

describe("EmptyState action", () => {
  it("renders the action as a primary button with a plus icon", () => {
    const { getByRole } = render(<EmptyState heading="No profiles" action={{ label: "New profile", onClick: () => {} }} />);
    const button = getByRole("button", { name: "New profile" });
    expect(button.querySelector("svg")).not.toBeNull();
  });
});
