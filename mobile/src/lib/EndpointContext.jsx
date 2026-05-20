import { createContext, useContext } from 'react';

export const EndpointContext = createContext(null);

export function useEndpoint() {
  const value = useContext(EndpointContext);
  if (!value) throw new Error('EndpointContext not provided');
  return value;
}
