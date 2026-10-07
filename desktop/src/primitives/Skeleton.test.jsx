import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Skeleton, { FLICKER_MS, SkeletonReader, SkeletonRows } from "./Skeleton.jsx";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("Skeleton placeholders", () => {
  it.each([
    ["rows", <SkeletonRows label="Loading connections" />, "status"],
    ["reader", <SkeletonReader label="Loading connections" />, "img"],
    ["value", <Skeleton label="Loading connections" />, "img"],
  ])("%s wait the flicker delay so a fast load never flashes", (_, node, role) => {
    render(node);
    act(() => vi.advanceTimersByTime(FLICKER_MS - 1));
    expect(screen.queryByRole(role)).toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole(role, { name: "Loading connections" })).toBeInTheDocument();
  });

  it("leaf placeholders are named images, never live regions; an unnamed reader is hidden", () => {
    const { container } = render(<><Skeleton delay={0} label="Loading usage" /><SkeletonReader delay={0} label="Loading file" /><SkeletonReader delay={0} /></>);
    expect(container.querySelectorAll("[role=status], [aria-live]")).toHaveLength(0);
    expect(screen.getAllByRole("img").map((n) => n.getAttribute("aria-label"))).toEqual(["Loading usage", "Loading file"]);
    expect(container.querySelectorAll("[aria-hidden=true][class*=reader]")).toHaveLength(1);
  });

  it("rows inside a listbox are presentation, not a second live region", () => {
    render(<ul role="listbox" aria-label="Skills"><SkeletonRows as="li" delay={0} /></ul>);
    const item = screen.getByRole("listbox", { hidden: true }).firstElementChild;
    expect(item.tagName).toBe("LI");
    expect(item.getAttribute("role")).toBe("presentation");
    expect(item.getAttribute("aria-hidden")).toBe("true");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("never nests a block line inside an inline element", () => {
    const { container } = render(<SkeletonRows delay={0} label="Loading" />);
    expect(container.querySelectorAll("span div, span > div")).toHaveLength(0);
    expect(container.querySelectorAll("[class*=skLine]").length).toBeGreaterThan(1);
  });
});
