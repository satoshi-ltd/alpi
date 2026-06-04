import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import AttachmentChips from "./AttachmentChips.jsx";

describe("AttachmentChips", () => {
  it("renders nothing when empty", () => {
    const { container } = render(<AttachmentChips items={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a card per file with name and human size", () => {
    render(
      <AttachmentChips
        items={[
          { path: "/a/shot.png", name: "shot.png", size: 2048 },
          { path: "/a/doc.pdf", name: "doc.pdf", size: 7428 * 1024 * 1024 },
        ]}
      />,
    );
    expect(screen.getByText("shot.png")).toBeTruthy();
    expect(screen.getByText("2 KB")).toBeTruthy();
    expect(screen.getByText("doc.pdf")).toBeTruthy();
    expect(screen.getByText("7428.0 MB")).toBeTruthy();
  });

  it("message variant caps at 4 cards and shows '+N more files'", () => {
    const items = Array.from({ length: 6 }, (_, i) => ({
      path: `/a/f${i}.pdf`, name: `f${i}.pdf`, mime: "application/pdf", size: 100,
    }));
    render(<AttachmentChips items={items} variant="message" />);
    expect(screen.getByText("f0.pdf")).toBeTruthy();
    expect(screen.getByText("f3.pdf")).toBeTruthy();
    expect(screen.queryByText("f4.pdf")).toBeNull();
    expect(screen.getByText("+2 more files")).toBeTruthy();
  });

  it("message variant has no remove button", () => {
    render(
      <AttachmentChips
        items={[{ path: "/a/x.pdf", name: "x.pdf", mime: "application/pdf", size: 1 }]}
        variant="message"
        onRemove={() => {}}
      />,
    );
    expect(screen.queryByLabelText("Remove x.pdf")).toBeNull();
  });

  it("calls onRemove with the index when the × is clicked", () => {
    const onRemove = vi.fn();
    render(
      <AttachmentChips
        items={[
          { path: "/a/one.png", name: "one.png", size: 10 },
          { path: "/a/two.pdf", name: "two.pdf", size: 20 },
        ]}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByLabelText("Remove two.pdf"));
    expect(onRemove).toHaveBeenCalledWith(1);
  });
});
