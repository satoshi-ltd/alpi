import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import StreamingMarkdown from "./StreamingMarkdown.jsx";

describe("StreamingMarkdown", () => {
  it("marks only the newest chunk, never text that was already on screen", () => {
    const { container, rerender } = render(<StreamingMarkdown source="Hello" />);
    rerender(<StreamingMarkdown source="Hello world" />);
    const chunks = [...container.querySelectorAll("[data-chunk]")].map((n) => n.textContent);
    expect(chunks.join("")).toBe(" world");
    expect(container.textContent.trim()).toBe("Hello world");
  });

  it("never re-marks earlier text when a render brings nothing new", () => {
    const { container, rerender } = render(<StreamingMarkdown source="Hi" />);
    rerender(<StreamingMarkdown source="Hi there" />);
    rerender(<StreamingMarkdown source="Hi there" />);
    const marked = [...container.querySelectorAll("[data-chunk]")].map((n) => n.textContent).join("");
    expect(marked).not.toContain("Hi");
  });

  it("still fades the new words when a re-parse shortens earlier text", () => {
    const { container, rerender } = render(<StreamingMarkdown source="a **bold" />);
    rerender(<StreamingMarkdown source="a **bold** and more" />);
    const marked = [...container.querySelectorAll("[data-chunk]")].map((n) => n.textContent).join("");
    expect(marked).toContain("and more");
  });
});
