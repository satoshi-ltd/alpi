import React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/sidebarPref', () => ({
  loadSidebarPref: async () => null,
  saveSidebarPref: async () => {},
}));

import { useSidebarOpen } from './useSidebarOpen';

afterEach(cleanup);

let seen = null;
function Probe({ width, height, twoPane }) {
  seen = useSidebarOpen(width, twoPane, height);
  return null;
}

describe('useSidebarOpen', () => {
  it('opens the roster when an open fold turns to landscape and hides it again in portrait', async () => {
    const { rerender } = render(<Probe width={690} height={829} twoPane />);
    await act(async () => {});
    expect(seen.open).toBe(false);
    rerender(<Probe width={829} height={690} twoPane />);
    expect(seen.open).toBe(true);
    rerender(<Probe width={690} height={829} twoPane />);
    expect(seen.open).toBe(false);
  });

  it('leaves the roster alone across a Split View drag that keeps the orientation', async () => {
    const { rerender } = render(<Probe width={834} height={1194} twoPane />);
    await act(async () => {});
    expect(seen.open).toBe(true);
    rerender(<Probe width={700} height={1194} twoPane />);
    expect(seen.open).toBe(true);
  });

  it('treats a Split View drag across the aspect ratio as a drag, not a rotation', async () => {
    const { rerender } = render(<Probe width={1024} height={768} twoPane />);
    await act(async () => {});
    expect(seen.open).toBe(true);
    rerender(<Probe width={590} height={768} twoPane />);
    expect(seen.open).toBe(true);
  });

  it('lets the user toggle win over the width rule', async () => {
    const { rerender } = render(<Probe width={829} height={690} twoPane />);
    await act(async () => {});
    act(() => seen.toggle());
    expect(seen.open).toBe(false);
    rerender(<Probe width={690} height={829} twoPane />);
    rerender(<Probe width={829} height={690} twoPane />);
    expect(seen.open).toBe(false);
  });
});
