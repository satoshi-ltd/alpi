function round1(v) {
  const r = v >= 100 ? Math.round(v) : Math.round(v * 10) / 10;
  return String(r).replace(/\.0$/, "");
}

export function fmtTok(n) {
  const v = Number(n) || 0;
  if (v >= 1e6) return `${round1(v / 1e6)}M`;
  if (v >= 1e3) return `${round1(v / 1e3)}K`;
  return String(Math.round(v));
}

export function formatUsd(n) {
  return `$${(Number(n) || 0).toFixed(2)}`;
}

// Workgroup post cost line: sub-cent costs keep 4 decimals so free-tier runs don't all read "$0.00".
export function formatCostLine(cost) {
  const tok = typeof cost?.tokens === "number" ? cost.tokens : 0;
  const usd = typeof cost?.usd === "number" ? cost.usd : 0;
  const tokStr = tok >= 1000 ? `${(tok / 1000).toFixed(1)}K` : `${tok}`;
  const usdStr = usd >= 0.01 ? `$${usd.toFixed(2)}` : `$${usd.toFixed(4)}`;
  return `${tokStr} · ${usdStr}`;
}
