import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import ProducedImages from "./ProducedImages.jsx";

const IMG = {
  kind: "image",
  name: "hero.jpg",
  path: "/Users/x/.alpi/profiles/muse/out/hero.jpg",
};

beforeEach(() => {
  invoke.mockReset();
  invoke.mockResolvedValue(null);
});

describe("ProducedImages", () => {
  it("loads the thumb with the file's own dir as root (not getImageRoots)", async () => {
    invoke.mockResolvedValueOnce("data:image/jpeg;base64,ZZZ");
    render(<ProducedImages images={[IMG]} />);
    await waitFor(() =>
      expect(screen.getByRole("img")).toHaveAttribute("src", "data:image/jpeg;base64,ZZZ"),
    );
    expect(invoke).toHaveBeenCalledWith("attachment_thumb", expect.objectContaining({
      path: IMG.path,
      roots: ["/Users/x/.alpi/profiles/muse/out"],
    }));
  });

  it("opens the lightbox on click", async () => {
    invoke.mockResolvedValueOnce("data:image/jpeg;base64,ZZZ");
    render(<ProducedImages images={[IMG]} />);
    const img = await screen.findByRole("img");
    fireEvent.click(img.closest("button"));
    expect(await screen.findByLabelText("Close")).toBeInTheDocument();
  });

  it("renders nothing when there are no images", () => {
    const { container } = render(<ProducedImages images={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
