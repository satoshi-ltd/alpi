import { describe, it, expect, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useRef } from "react";
import SettingsNav, { activeSectionFor, settingsMatch } from "./SettingsNav.jsx";
import { Row, Section } from "./primitives.jsx";

function Page() {
  const ref = useRef(null);
  return (
    <div ref={ref} data-testid="scroller">
      <SettingsNav scrollRef={ref}>
        <Section title="Overview">
          <Row label="home">~/.alpi</Row>
          <Row label="vision model">none</Row>
        </Section>
        <Section title="MCP Servers">
          <Row label="servers">github</Row>
        </Section>
        <Section title="Email">
          <Row label="accounts">none</Row>
        </Section>
      </SettingsNav>
    </div>
  );
}

const rail = () => screen.getByRole("navigation", { name: "Settings sections" });
const railItems = () => within(rail()).getAllByRole("button").map((b) => b.textContent);

describe("settings rail", () => {
  it("lists every section in page order", () => {
    render(<Page />);
    expect(railItems()).toEqual(["Overview", "MCP Servers", "Email"]);
  });

  it("filters sections and rows by label, keeping a section whose title matches whole", async () => {
    render(<Page />);
    const search = screen.getByRole("searchbox", { name: "Search settings" });
    fireEvent.change(search, { target: { value: "vision" } });
    await waitFor(() => expect(railItems()).toEqual(["Overview"]));
    expect(screen.getByText("vision model").closest("[data-settings-row]").hidden).toBe(false);
    expect(screen.getByText("home").closest("[data-settings-row]").hidden).toBe(true);

    fireEvent.change(search, { target: { value: "mcp" } });
    await waitFor(() => expect(railItems()).toEqual(["MCP Servers"]));
    expect(screen.getByText("servers").closest("[data-settings-row]").hidden).toBe(false);

    fireEvent.change(search, { target: { value: "zzz" } });
    await waitFor(() => expect(screen.getByText(/No settings match/)).toBeInTheDocument());

    fireEvent.keyDown(search, { key: "Escape" });
    expect(search.value).toBe("");
    await waitFor(() => expect(railItems()).toHaveLength(3));
  });

  it("jumps to the first match on Enter and marks it current", async () => {
    const spy = vi.fn();
    Element.prototype.scrollIntoView = spy;
    render(<Page />);
    const search = screen.getByRole("searchbox", { name: "Search settings" });
    fireEvent.change(search, { target: { value: "accounts" } });
    await waitFor(() => expect(railItems()).toEqual(["Email"]));
    fireEvent.keyDown(search, { key: "Enter" });
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.contexts[0].id).toBe("settings-email");
    expect(within(rail()).getByRole("button", { name: "Email" })).toHaveAttribute("aria-current", "true");
    delete Element.prototype.scrollIntoView;
  });

  it("highlights the section scrolled under the top edge", () => {
    render(<Page />);
    const tops = { "settings-overview": -400, "settings-mcp-servers": 10, "settings-email": 300 };
    for (const [id, top] of Object.entries(tops)) {
      document.getElementById(id).getBoundingClientRect = () => ({ top });
    }
    act(() => {
      fireEvent.scroll(screen.getByTestId("scroller"));
    });
    expect(within(rail()).getByRole("button", { name: "MCP Servers" })).toHaveAttribute("aria-current", "true");
    expect(activeSectionFor([], null)).toBeNull();
  });
});

describe("settingsMatch", () => {
  it("matches case-insensitively and treats an empty query as a match", () => {
    expect(settingsMatch("Vision model", "MODEL")).toBe(true);
    expect(settingsMatch("home", "")).toBe(true);
    expect(settingsMatch("home", "x")).toBe(false);
  });
});
