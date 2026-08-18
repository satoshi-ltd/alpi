import { createContext, useContext } from 'react';

export const PaneContext = createContext({ twoPane: false, side: 'full' });

export function usePane() {
  return useContext(PaneContext);
}
