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
  it("shows placeholder rows, never the word, before skills resolve", async () => {
    h.invoke.mockImplementation(() => new Promise(() => {}));
    render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    expect(screen.getByRole("progressbar", { name: "Loading skills" })).toBeTruthy();
    await waitFor(() => expect(document.querySelectorAll("[role=listbox] li[role=presentation] [class*=listRow]").length).toBeGreaterThan(1));
    expect(screen.queryByRole("status", { name: "Loading skills" })).toBeNull();
    expect(document.body.textContent).not.toMatch(/Loading/);
    expect(screen.queryByText("No skills installed")).toBeNull();
  });

  it("loads the list and threads connectionId into list + detail RPCs", async () => {
    render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_skills", { profile: "muse", connectionId: "c2" }));
    expect((await screen.findAllByText("make-logo-svg")).length).toBeGreaterThan(0);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith(
      "profile_skill_read",
      expect.objectContaining({ profile: "muse", name: "make-logo-svg", connectionId: "c2" }),
    ));
  });

  it("keys requirements by kind and name and marks missing only the unresolved one", async () => {
    const requires = [{ kind: "env", name: "TOKEN", resolved: true }, { kind: "bin", name: "TOKEN", resolved: false }];
    h.invoke.mockImplementation((cmd) => {
      if (cmd === "profile_skills") return Promise.resolve(SKILLS);
      if (cmd === "profile_skill_read") return Promise.resolve({ ...DETAIL, requires });
      return Promise.resolve(null);
    });
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    const req = await waitFor(() => {
      const dt = Array.from(document.querySelectorAll("dt")).find((d) => d.textContent === "Requires");
      expect(dt).toBeTruthy();
      return dt.nextElementSibling;
    });
    expect(Array.from(req.querySelectorAll("code")).map((c) => c.textContent)).toEqual(["TOKEN", "TOKEN"]);
    expect(req.querySelectorAll("[class*=idMissing]")).toHaveLength(1);
    expect(req.textContent).toBe("TOKEN, TOKEN missing");
    expect(errors.mock.calls.some((c) => /same key/.test(String(c[0])))).toBe(false);
    errors.mockRestore();
  });

  it("re-fetches against the new daemon when the connection changes", async () => {
    const { rerender } = render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_skills", { profile: "muse", connectionId: "c2" }));
    h.invoke.mockClear();
    rerender(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c9" />);
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_skills", { profile: "muse", connectionId: "c9" }));
  });

  it("starts every row with the skill's name in sans, its size or state the one trailing meta, never a pill or a fade", async () => {
    render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    const options = await screen.findAllByRole("option");
    expect(options).toHaveLength(2);
    for (const [i, option] of options.entries()) {
      expect(option.querySelector("[class*=rowTitle]").textContent).toBe(SKILLS[i].name);
      expect(option.querySelectorAll("[class*=rowMeta]")).toHaveLength(1);
      expect(option.querySelector("[class*=sizeTag]")).toBeNull();
      expect(option.className).not.toMatch(/Muted/);
    }
    expect(options[0].querySelector("[class*=rowMeta]").textContent).toBe("2.3 KB");
    expect(options[1].querySelector("[class*=rowMeta]").textContent).toBe("inactive");
    expect(options[1].querySelector("[class*=rowTitle]").className).toMatch(/rowOff/);
    expect(screen.getByText("Creative")).toBeTruthy();
    await screen.findByRole("heading", { name: "make-logo-svg" });
    expect(screen.getByRole("button", { name: "Copy creative/make-logo-svg" })).toBeTruthy();
    const labels = Array.from(document.querySelectorAll("dt")).map((d) => d.textContent);
    expect(labels).toEqual(["About", "Tools", "Keywords", "Version"]);
    expect(screen.getByText("v0.1.1 · user · Jun 5")).toBeTruthy();
    expect(screen.getByText("read_file").tagName).toBe("CODE");
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
    await waitFor(() => expect(document.querySelector("[aria-hidden=true][class*=reader]")).not.toBeNull());
    expect(document.body.textContent).not.toMatch(/Loading/);
  });

  it("reads a file that is still loading as placeholder lines, never the word", async () => {
    const tree = [...DETAIL.tree, { name: "run.py", kind: "file", ftype: "py", size: 10 }];
    h.invoke.mockImplementation((cmd) => {
      if (cmd === "profile_skills") return Promise.resolve(SKILLS);
      if (cmd === "profile_skill_read") return Promise.resolve({ ...DETAIL, tree });
      if (cmd === "profile_skill_file") return new Promise(() => {});
      return Promise.resolve(null);
    });
    render(<SkillsModal open onClose={() => {}} profile="muse" connectionId="c2" />);
    fireEvent.click(await screen.findByText("run.py"));
    const placeholder = await screen.findByRole("img", { name: "Loading file" });
    expect(placeholder.querySelectorAll("[class*=skLine]").length).toBeGreaterThan(1);
    expect(document.body.textContent).not.toMatch(/Loading/);
  });
});
