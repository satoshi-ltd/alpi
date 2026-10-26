import { useRef } from 'react';

export function useReveal(bonesShown) {
  const had = useRef(false);
  if (bonesShown) had.current = true;
  return had.current && !bonesShown;
}
