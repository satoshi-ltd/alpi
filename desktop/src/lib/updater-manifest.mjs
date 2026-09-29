const REPO_RELEASES = "https://github.com/satoshi-ltd/alpi/releases/download";

export function assetName(url) {
  const path = String(url || "").split("?")[0];
  return decodeURIComponent(path.slice(path.lastIndexOf("/") + 1));
}

// tauri-action writes `releases/latest/download/<asset>` when it only knows a release id; on this repo "latest" is whichever alpi CLI release shipped last, so those URLs 404.
export function pinManifest(manifest, tag, availableAssets) {
  const available = new Set(availableAssets);
  const platforms = manifest?.platforms ?? {};
  const missing = [];
  const out = { ...manifest, platforms: {} };
  for (const [platform, entry] of Object.entries(platforms)) {
    const name = assetName(entry?.url);
    if (!name || !available.has(name)) missing.push(`${platform}: ${name || "(no url)"}`);
    out.platforms[platform] = { ...entry, url: `${REPO_RELEASES}/${tag}/${encodeURIComponent(name)}` };
  }
  return { manifest: out, missing };
}
