import { useCallback, useEffect, useRef } from 'react';

import { DURATION_OUT, UNMOUNT_BUFFER } from '../../components/useSheetGesture';

// iOS drops a Modal presented while another is still dismissing; wait out the ActionSheet exit first.
export function useModalHandoff() {
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  return useCallback((fn) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(fn, DURATION_OUT + UNMOUNT_BUFFER);
  }, []);
}
