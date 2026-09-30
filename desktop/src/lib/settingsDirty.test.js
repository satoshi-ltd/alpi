import { describe, expect, it } from "vitest";
import { hasDirtySettings, setSettingsDirty } from "./settingsDirty.js";

describe("settings dirty registry", () => {
  it("is dirty while any key is dirty", () => {
    expect(hasDirtySettings()).toBe(false);
    setSettingsDirty("a", true);
    setSettingsDirty("b", true);
    setSettingsDirty("a", false);
    expect(hasDirtySettings()).toBe(true);
    setSettingsDirty("b", false);
    expect(hasDirtySettings()).toBe(false);
  });
});
