import { useEffect, useRef } from 'react';

export function useFireOnce(signal, onTrigger) {
  const firedRef = useRef(false);
  useEffect(() => {
    if (!signal || firedRef.current) return;
    firedRef.current = true;
    onTrigger();
  }, [signal, onTrigger]);
}
