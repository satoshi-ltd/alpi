import { useCallback, useEffect, useRef, useState } from 'react';

import { sidebarOpenByDefault } from '../lib/panes';
import { loadSidebarPref, saveSidebarPref } from '../lib/sidebarPref';

// The width rule decides only on entering two panes or on a rotation; a Split View drag afterwards never hides a roster the user still has.
export function useSidebarOpen(width, twoPane, height = 0) {
  const [pref, setPref] = useState(null);
  const [auto, setAuto] = useState(() => sidebarOpenByDefault(width, height));
  const wasTwoPane = useRef(twoPane);
  const landscape = width > height;
  const wasLandscape = useRef(landscape);
  const wasHeight = useRef(height);

  useEffect(() => {
    let alive = true;
    loadSidebarPref().then((value) => {
      if (alive && value !== null) setPref(value);
    });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const rotated = landscape !== wasLandscape.current && height !== wasHeight.current;
    if (twoPane && (!wasTwoPane.current || rotated)) setAuto(sidebarOpenByDefault(width, height));
    wasTwoPane.current = twoPane;
    wasLandscape.current = landscape;
    wasHeight.current = height;
  }, [twoPane, width, height, landscape]);

  const open = pref ?? auto;

  const toggle = useCallback(() => {
    const next = !open;
    setPref(next);
    saveSidebarPref(next);
  }, [open]);

  return { open, toggle };
}
