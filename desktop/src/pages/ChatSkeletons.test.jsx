import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { SkParagraph } from "../primitives/Skeleton.jsx";
import { ChatLoadSkeleton, PendingReplySkeleton } from "./ChatSkeletons.jsx";

// Every shimmer line carries an inline animation-delay — a stable hook to count/inspect them (CSS-module classes are stripped under css:false).
const lines = (el) => [...el.querySelectorAll('[style*="animation-delay"]')];

describe("SkParagraph", () => {
  it("renders one line per width, in order, staggered by 0.12s", () => {
    const { container } = render(<SkParagraph widths={["88%", "100%", "62%"]} />);
    const ls = lines(container);
    expect(ls).toHaveLength(3);
    expect(ls.map((l) => l.style.width)).toEqual(["88%", "100%", "62%"]);
    expect(ls.map((l) => l.style.animationDelay)).toEqual(["0s", "0.12s", "0.24s"]);
  });

  it("keeps high indices clean (no float noise) in the delay", () => {
    const { container } = render(<SkParagraph widths={["1%", "1%", "1%", "1%"]} />);
    expect(lines(container)[3].style.animationDelay).toBe("0.36s");
  });
});

describe("ChatLoadSkeleton", () => {
  it("renders the conversation-shaped block (agent · bubble · agent · agent) and fades in", () => {
    const { container } = render(<ChatLoadSkeleton />);
    const ls = lines(container);
    expect(ls).toHaveLength(4 + 2 + 5 + 2);
    const widths = ls.map((l) => l.style.width);
    expect(widths[0]).toBe("88%"); // first agent paragraph leads wide
    expect(widths).toContain("62%"); // …and ends short (varied, never a barcode)
    expect(widths).toContain("90%"); // the user-bubble paragraph
    expect(container.querySelector(".anim-fade")).not.toBeNull();
  });
});

describe("PendingReplySkeleton", () => {
  it("shows a 'thinking…' status + a 3-line paragraph, fades in, no spinner", () => {
    const { container, getByText } = render(<PendingReplySkeleton />);
    expect(getByText("thinking…")).toBeTruthy();
    expect(lines(container)).toHaveLength(3);
    expect(container.querySelector(".anim-fade")).not.toBeNull();
  });
});
