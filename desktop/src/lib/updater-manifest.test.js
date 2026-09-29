import { describe, expect, it } from "vitest";

import { assetName, pinManifest } from "./updater-manifest.mjs";

const MANIFEST = {
  version: "0.6.3",
  notes: "",
  pub_date: "2026-09-29T00:00:00Z",
  platforms: {
    "darwin-aarch64": { signature: "sigA", url: "https://github.com/satoshi-ltd/alpi/releases/latest/download/Alpi_universal.app.tar.gz" },
    "linux-x86_64": { signature: "sigL", url: "https://github.com/satoshi-ltd/alpi/releases/latest/download/Alpi_0.6.3_amd64.AppImage" },
    "windows-x86_64": { signature: "sigW", url: "https://github.com/satoshi-ltd/alpi/releases/latest/download/Alpi_0.6.3_x64-setup.exe" },
  },
};

describe("pinManifest", () => {
  it("points every platform at the versioned desktop release, keeping signatures", () => {
    const { manifest, missing } = pinManifest(MANIFEST, "desktop-v0.6.3", [
      "Alpi_universal.app.tar.gz",
      "Alpi_0.6.3_amd64.AppImage",
      "Alpi_0.6.3_x64-setup.exe",
      "latest.json",
    ]);
    expect(missing).toEqual([]);
    expect(manifest.version).toBe("0.6.3");
    expect(manifest.platforms["darwin-aarch64"]).toEqual({
      signature: "sigA",
      url: "https://github.com/satoshi-ltd/alpi/releases/download/desktop-v0.6.3/Alpi_universal.app.tar.gz",
    });
    expect(manifest.platforms["windows-x86_64"].url).toBe(
      "https://github.com/satoshi-ltd/alpi/releases/download/desktop-v0.6.3/Alpi_0.6.3_x64-setup.exe",
    );
    expect(MANIFEST.platforms["darwin-aarch64"].url).toMatch("releases/latest/download");
  });

  it("names every platform whose asset is not in the release", () => {
    const { missing } = pinManifest(MANIFEST, "desktop-v0.6.3", ["Alpi_universal.app.tar.gz"]);
    expect(missing).toEqual([
      "linux-x86_64: Alpi_0.6.3_amd64.AppImage",
      "windows-x86_64: Alpi_0.6.3_x64-setup.exe",
    ]);
  });

  it("reads the asset name off any release URL shape", () => {
    expect(assetName("https://github.com/o/r/releases/download/desktop-v0.6.2/Alpi_universal.app.tar.gz?x=1")).toBe("Alpi_universal.app.tar.gz");
    expect(assetName("https://github.com/o/r/releases/latest/download/Alpi%200.6.3.dmg")).toBe("Alpi 0.6.3.dmg");
    expect(assetName("")).toBe("");
  });
});
