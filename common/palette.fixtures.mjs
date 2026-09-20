export function contrastRatio(foreground, background) {
  const luminance = (color) => {
    const channels = color.startsWith("#")
      ? [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16))
      : color.match(/[\d.]+/g).slice(0, 3).map(Number);
    const rgb = channels.map((n) => n / 255).map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  };
  const a = luminance(foreground);
  const b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
