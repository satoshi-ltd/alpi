import { useCallback, useEffect, useRef, useState } from 'react';

import { sidebarOpenByDefault } from '../lib/panes';
import { loadSidebarPref, saveSidebarPref } from '../lib/sidebarPref';

// The width rule decides only on entering two panes; a Split View drag afterwards never hides a roster the user still has.
export function useSidebarOpen(width, twoPane) {
  const [pref, setPref] = useState(null);
  const [auto, setAuto] = useState(() => sidebarOpenByDefault(width));
  const wasTwoPane = useRef(twoPane);

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
    if (twoPane && !wasTwoPane.current) setAuto(sidebarOpenByDefault(width));
    wasTwoPane.current = twoPane;
  }, [twoPane, width]);

  const open = pref ?? auto;

  const toggle = useCallback(() => {
    const next = !open;
    setPref(next);
    saveSidebarPref(next);
  }, [open]);

  return { open, toggle };
}
