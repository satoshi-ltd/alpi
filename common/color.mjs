export function mixHex(color, amount, base) {
  const channels = (hex) => {
    if (!/^#(?:[\da-f]{3}|[\da-f]{6})$/i.test(hex ?? "")) return null;
    const value = hex.length === 4 ? hex.slice(1).split("").map((c) => c + c).join("") : hex.slice(1);
    return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16));
  };
  const foreground = channels(color);
  const background = channels(base);
  if (!foreground || !background) return base;
  const weight = Math.max(0, Math.min(1, Number(amount) || 0));
  return `rgb(${foreground.map((value, i) => Math.round(value * weight + background[i] * (1 - weight))).join(",")})`;
}

export function contrastText(hex) {
  if (!/^#(?:[\da-f]{3}|[\da-f]{6})$/i.test(hex ?? "")) return "#ffffff";
  const value = hex.length === 4 ? hex.slice(1).split("").map((c) => c + c).join("") : hex.slice(1);
  const rgb = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16) / 255)
    .map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  const luminance = rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  return (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) ? "#000000" : "#ffffff";
}
