import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useColorScheme } from 'react-native';

import { loadThemePref, saveThemePref } from '../lib/themePref';
import { palettes, shadows, fonts, fontSizes, lineHeights, mobile, alpha, motion } from './tokens';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const osScheme = useColorScheme();
  const [pref, setPref] = useState('system');
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadThemePref().then((value) => {
      if (cancelled) return;
      setPref(value ?? 'system');
      setHydrated(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const mode = pref === 'system' ? (osScheme === 'dark' ? 'dark' : 'light') : pref;
  const colors = palettes[mode];
  const shadow = shadows[mode];

  const setMode = useCallback((next) => {
    setPref(next);
    saveThemePref(next);
  }, []);

  const value = useMemo(
    () => ({
      mode,
      pref,
      setMode,
      colors,
      shadow,
      fonts,
      fontSizes,
      lineHeights,
      mobile,
      alpha,
      motion,
      hydrated,
    }),
    [mode, pref, setMode, colors, shadow, hydrated],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider');
  return ctx;
}
