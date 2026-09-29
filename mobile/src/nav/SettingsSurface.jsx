import { createContext, useContext } from 'react';

import { usePane } from './PaneContext';

const SettingsSurfaceContext = createContext(false);

export function SettingsSurface({ children }) {
  return <SettingsSurfaceContext.Provider value={true}>{children}</SettingsSurfaceContext.Provider>;
}

// Wide settings render the desktop field grid; every other surface keeps the phone rows even on a tablet.
export function useWideSettings() {
  const { twoPane } = usePane();
  const inSurface = useContext(SettingsSurfaceContext);
  return twoPane && inSurface;
}
