import { useEffect, useLayoutEffect, useState } from "react";

// Viewport-fixed positioning for anchored popovers.
export default function useAutoPosition({
  open,
  anchorRef,
  popoverRef,
  direction = "down",
  align = "left",
  margin = 12,
  gap = 6,
}) {
  const [resolved, setResolved] = useState({
    direction,
    align,
    top: 0,
    left: 0,
    maxWidth: null,
    ready: false,
  });

  // Recompute while open so the popover tracks scroll and resize.
  const compute = () => {
    if (!anchorRef.current || !popoverRef.current) return;
    const a = anchorRef.current.getBoundingClientRect();
    const p = popoverRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // Prefer the requested side and flip if needed.
    let dir = direction;
    const fitsBelow = a.bottom + p.height + margin <= vh;
    const fitsAbove = a.top - p.height - margin >= 0;
    if (dir === "down" && !fitsBelow && fitsAbove) dir = "up";
    if (dir === "up" && !fitsAbove && fitsBelow) dir = "down";

    // Pick the horizontal side with more room.
    const roomRight = vw - a.left - margin;
    const roomLeft = a.right - margin;
    let al = align;
    if (roomRight < p.width && roomLeft > roomRight) al = "right";
    if (roomLeft < p.width && roomRight > roomLeft) al = "left";
    const availableWidth = Math.max(0, al === "left" ? roomRight : roomLeft);

    const effW = Math.min(p.width, availableWidth);

    let left;
    if (al === "left") {
      left = Math.max(margin, a.left);
      if (left + effW + margin > vw) left = vw - effW - margin;
    } else {
      left = Math.max(margin, a.right - effW);
    }

    let top;
    if (dir === "down") {
      top = a.bottom + gap;
      if (top + p.height + margin > vh) top = vh - p.height - margin;
    } else {
      top = a.top - p.height - gap;
      if (top < margin) top = margin;
    }

    setResolved({
      direction: dir,
      align: al,
      top,
      left,
      maxWidth: availableWidth > 0 ? availableWidth : null,
      ready: true,
    });
  };

  useLayoutEffect(() => {
    if (!open) {
      setResolved((r) => ({ ...r, ready: false }));
      return;
    }
    compute();
  }, [open, direction, align, margin, gap]);

  // Keep the popover aligned while open.
  useEffect(() => {
    if (!open) return;
    const onScrollOrResize = () => compute();
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [open]);

  return resolved;
}
