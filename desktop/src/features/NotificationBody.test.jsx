import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const openUrl = vi.fn(() => Promise.resolve());
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: (...args) => openUrl(...args) }));

import NotificationBody from "./NotificationBody.jsx";

beforeEach(() => openUrl.mockClear());

describe("NotificationBody links", () => {
  it("renders a markdown link and a bare URL as anchors that open in the system browser", () => {
    render(<NotificationBody body={"Ver [el anuncio](https://example.com/a) hoy.\nhttps://example.com/b."} />);
    const named = screen.getByRole("link", { name: "el anuncio" });
    expect(named.getAttribute("href")).toBe("https://example.com/a");
    const bare = screen.getByRole("link", { name: "https://example.com/b" });
    expect(bare.getAttribute("href")).toBe("https://example.com/b");
    const event = fireEvent.click(bare);
    expect(event).toBe(false);
    expect(openUrl).toHaveBeenCalledWith("https://example.com/b");
  });

  it("keeps a URL inside code as code", () => {
    render(<NotificationBody body={"Usa `https://example.com/c` tal cual."} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("https://example.com/c").tagName).toBe("CODE");
  });
});
