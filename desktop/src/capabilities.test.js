import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const DIR = join(__dirname, "..", "src-tauri", "capabilities");
const capabilities = readdirSync(DIR).filter((f) => f.endsWith(".json")).map((f) => JSON.parse(readFileSync(join(DIR, f), "utf8")));

describe("Tauri capabilities", () => {
  it("grants printing to the main window only", () => {
    const printing = capabilities.filter((c) => c.permissions.includes("core:webview:allow-print"));
    expect(printing).toHaveLength(1);
    expect(printing[0].windows).toEqual(["main"]);
  });
});
