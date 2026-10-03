import { createContext, useContext } from 'react';

import { useTheme } from '../theme/ThemeContext';

export const GroupToneContext = createContext(null);

export function groupTone(colors, mode) {
  return mode === 'dark' ? colors.bgPane : colors.bgSide;
}

export function useGroundTone() {
  const { colors } = useTheme();
  return useContext(GroupToneContext) ?? colors.bgPane;
}
