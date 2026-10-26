import { createContext, useContext } from 'react';

import { useTheme } from '../theme/ThemeContext';

export const GroupToneContext = createContext(null);

export function groupTone(colors) {
  return colors.card;
}

export function useGroundTone() {
  const { colors } = useTheme();
  return useContext(GroupToneContext) ?? colors.bgPane;
}
