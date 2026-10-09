import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useColorScheme, useWindowDimensions } from 'react-native';

import { loadThemePref, saveThemePref } from '../lib/themePref';
import { chromeFontMultiplier, clampTextScale, DEFAULT_TEXT_SCALE, scaleFontSizes } from './textScale';
import { loadTextScale, saveTextScale } from './textScalePref';
import { palettes, shadows, fonts, lineHeights, mobile, alpha, motion } from './tokens';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const osScheme = useColorScheme();
  const [pref, setPref] = useState('system');
  const [textScale, setTextScaleState] = useState(DEFAULT_TEXT_SCALE);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadThemePref(), loadTextScale()])
      .then(([theme, scale]) => {
        if (cancelled) return;
        setPref(theme ?? 'system');
        setTextScaleState(clampTextScale(scale));
        setHydrated(true);
      })
      .catch(() => {
        if (!cancelled) setHydrated(true);
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
    Promise.resolve(saveThemePref(next)).catch(() => {});
  }, []);

  const setTextScale = useCallback((next) => {
    const value = clampTextScale(next);
    setTextScaleState(value);
    Promise.resolve(saveTextScale(value)).catch(() => {});
  }, []);

  const { fontScale = 1 } = useWindowDimensions();
  const fontSizes = useMemo(() => scaleFontSizes(textScale), [textScale]);
  const chromeScale = chromeFontMultiplier(textScale);

  const value = useMemo(
    () => ({
      mode,
      pref,
      setMode,
      colors,
      shadow,
      fonts,
      fontSizes,
      textScale,
      fontScale,
      chromeScale,
      setTextScale,
      lineHeights,
      mobile,
      alpha,
      motion,
      hydrated,
    }),
    [mode, pref, setMode, colors, shadow, fontSizes, textScale, fontScale, chromeScale, setTextScale, hydrated],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider');
  return ctx;
}
