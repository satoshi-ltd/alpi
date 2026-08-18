import { useRef } from 'react';

// Consumers null the target that feeds a sheet in the same update that flips `open` false, so without this the surface empties on frame 1 of its exit animation.
export function useExitSnapshot(open, current) {
  const held = useRef(current);
  if (open) held.current = current;
  return open ? current : held.current;
}
