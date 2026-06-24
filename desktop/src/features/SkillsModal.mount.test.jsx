import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));

import SkillsModal from "./SkillsModal.jsx";

const SKILLS = [
  { name: "make-logo-svg", category: "creative", description: "Author a logo", size: 2400, status: "active", reason: "", keywords: ["logo"] },
  { name: "whoop", category: "personal", description: "Sync WHOOP", size: 3400, status: "inactive", reason: "missing env X", keywords: ["whoop"] },
];
const DETAIL = {
  category: "creative", name: "make-logo-svg", description: "Author a logo", path: "/x/SKILL.md",
  version: "0.1.1", origin: "user", created_at: "2026-06-05", status: "active", reason: "",
  requires: [], platforms: [], tools: ["read_file"], keywords: ["logo"],
  tree: [{ name: "SKILL.md", kind: "file", ftype: "skill", size: 100 }], size: 2400, body: "# When\n\nuse it",
};

beforeEach(() => {
  h.invoke.mockReset();
  h.invoke.mockImplementation((cmd) => {
    if (cmd === "profile_skills") return Promise.resolve(SKILLS);
    if (cmd === "profile_skill_read") return Promise.resolve(DETAIL);
    if (cmd === "profile_skill_file") return Promise.resolve({ ftype: "py", binary: false, text: "x", size: 1 });
    return Promise.resolve(null);
  });
});

describe("SkillsModal (mounted)", () => {
  it("loads the list and threads connectionId into list + detail RPCs", async () => {
    render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_skills", { profile: "muse", connectionId: "c2" }));
    expect((await screen.findAllByText("make-logo-svg")).length).toBeGreaterThan(0);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith(
      "profile_skill_read",
      expect.objectContaining({ profile: "muse", name: "make-logo-svg", connectionId: "c2" }),
    ));
  });

  it("re-fetches against the new daemon when the connection changes", async () => {
    const { rerender } = render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_skills", { profile: "muse", connectionId: "c2" }));
    h.invoke.mockClear();
    rerender(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c9" />);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_skills", { profile: "muse", connectionId: "c9" }));
  });

  it("shows an empty state when no skills are installed", async () => {
    h.invoke.mockImplementation((cmd) => (cmd === "profile_skills" ? Promise.resolve([]) : Promise.resolve(null)));
    render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    expect(await screen.findByText("No skills installed")).toBeTruthy();
  });

  it("drops the previous daemon's content the moment the connection changes", async () => {
    h.invoke.mockImplementation((cmd, args) => {
      if (cmd === "profile_skills") return args.connectionId === "c2" ? Promise.resolve(SKILLS) : new Promise(() => {});
      if (cmd === "profile_skill_read") return Promise.resolve(DETAIL);
      return Promise.resolve(null);
    });
    const Harness = ({ cid }) => (
      <SkillsModal key={`${cid}:muse`} open onClose={() => {}} profile="muse" connectionId={cid} />
    );
    const { rerender } = render(<Harness cid="c2" />);
    expect((await screen.findAllByText("make-logo-svg")).length).toBeGreaterThan(0);
    rerender(<Harness cid="c9" />);
    await waitFor(() => expect(screen.queryByText("make-logo-svg")).toBeNull());
  });

  it("clears the previous detail when selecting another skill", async () => {
    h.invoke.mockImplementation((cmd, args) => {
      if (cmd === "profile_skills") return Promise.resolve(SKILLS);
      if (cmd === "profile_skill_read") return args.name === "make-logo-svg" ? Promise.resolve(DETAIL) : new Promise(() => {});
      return Promise.resolve(null);
    });
    render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    await waitFor(() => expect(document.body.textContent).toContain("use it"));
    fireEvent.click(screen.getByText("whoop"));
    await waitFor(() => expect(document.body.textContent).not.toContain("use it"));
  });
});
