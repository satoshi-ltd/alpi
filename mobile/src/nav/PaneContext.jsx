import { createContext, useContext } from 'react';

export const PaneContext = createContext({
  twoPane: false,
  side: 'full',
  sidebarOpen: true,
  toggleSidebar: () => {},
});

export function usePane() {
  return useContext(PaneContext);
}
