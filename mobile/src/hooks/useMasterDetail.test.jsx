import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, renderHook } from '@testing-library/react';
import React from 'react';

const h = vi.hoisted(() => ({ width: 390 }));

vi.mock('react-native', () => ({ useWindowDimensions: () => ({ width: h.width, height: 900 }) }));

import { PaneContext } from '../nav/PaneContext';
import { useMasterDetail } from './useMasterDetail';

afterEach(cleanup);

function at(width, pane) {
  h.width = width;
  const wrapper = ({ children }) => <PaneContext.Provider value={pane}>{children}</PaneContext.Provider>;
  return renderHook(() => useMasterDetail(), { wrapper }).result.current;
}

describe('master-detail on the pane the screen really has', () => {
  it('stays a phone below two panes', () => {
    expect(at(390, { twoPane: false, sidebarOpen: true })).toBe(false);
    expect(at(900, { twoPane: false, sidebarOpen: false })).toBe(false);
  });

  it('judges an open fold by its pane, not by its window', () => {
    expect(at(852, { twoPane: true, sidebarOpen: true })).toBe(false);
    expect(at(852, { twoPane: true, sidebarOpen: false })).toBe(true);
    expect(at(1104, { twoPane: true, sidebarOpen: true })).toBe(true);
    expect(at(1039, { twoPane: true, sidebarOpen: true })).toBe(false);
    expect(at(1040, { twoPane: true, sidebarOpen: true })).toBe(true);
  });
});
