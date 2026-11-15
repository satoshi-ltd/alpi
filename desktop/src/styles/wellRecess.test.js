import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const read = (rel) => readFileSync(join(SRC, rel), "utf8");
const TOKENS = read("styles/tokens.css");
const block = (css, selector) => new RegExp(`(^|\\n)${selector.replace(/[.[\]()]/g, "\\$&")} \\{([^}]*)\\}`).exec(css)?.[2] ?? "";

describe("wells that sit on another fill", () => {
  it("recess wells inside floats to the pane in dark, like the phone's recess(), and keep the card well in light", () => {
    const vars = [...TOKENS.matchAll(/--well-float:\s*([^;]+);/g)].map((m) => m[1]);
    expect(vars).toEqual(["var(--card)", "var(--bg-pane)", "var(--bg-pane)"]);
    for (const [file, selector] of [
      ["primitives/Modal.module.css", ".modal"],
      ["primitives/BrowseModal.module.css", ".modal"],
      ["primitives/Panels.module.css", ".shell"],
      ["features/sessions/ManageSessionsModal.module.css", ".modal"],
      ["primitives/ModelPicker.module.css", ".modelPickerPop"],
      ["primitives/Dropdown.module.css", ".menu"],
    ]) {
      const body = block(read(file), selector);
      expect(body, file).toMatch(/background: var\(--bg-elev\);/);
      expect(body, file).toMatch(/--well: var\(--well-float\);/);
      expect(body, file).toMatch(/--well-focus: var\(--well-float\);/);
    }
  });

  it("recesses the fields and secondary choices of an inline request, and code in a user bubble, to the pane", () => {
    expect(TOKENS).toMatch(/--well-nested: var\(--bg-pane\);/);
    const card = block(read("features/InlineRequest.module.css"), ".card");
    expect(card).toMatch(/background: var\(--card\);/);
    for (const v of ["--fill", "--well", "--well-focus"]) expect(card).toMatch(new RegExp(`${v}: var\\(--well-nested\\);`));
    expect(block(read("primitives/Message.module.css"), ".bubble .md pre")).toMatch(/background: var\(--well-nested\);/);
  });
});
