import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';

import { EndpointContext } from '../lib/EndpointContext';
import { useActiveRole, useCanAdminEarly, useIsAdmin } from './useActiveRole';

function wrap(value) {
  return function Wrapper({ children }) {
    return <EndpointContext.Provider value={value}>{children}</EndpointContext.Provider>;
  };
}

describe('useActiveRole', () => {
  it.each([
    ['admin', 'admin'],
    ['member', 'member'],
    [null, null],
  ])('returns role=%s', (role, expected) => {
    const { result } = renderHook(() => useActiveRole(), { wrapper: wrap({ activeRole: role }) });
    expect(result.current).toBe(expected);
  });
});

describe('useCanAdminEarly · chrome-permissive', () => {
  it('true for admin', () => {
    const { result } = renderHook(() => useCanAdminEarly(), { wrapper: wrap({ activeRole: 'admin' }) });
    expect(result.current).toBe(true);
  });
  it('true for null (probe pending, treat as admin-equiv to avoid UI flicker)', () => {
    const { result } = renderHook(() => useCanAdminEarly(), { wrapper: wrap({ activeRole: null }) });
    expect(result.current).toBe(true);
  });
  it('false for member', () => {
    const { result } = renderHook(() => useCanAdminEarly(), { wrapper: wrap({ activeRole: 'member' }) });
    expect(result.current).toBe(false);
  });
});

describe('useIsAdmin · strict route-guard', () => {
  it('true only for admin', () => {
    const { result } = renderHook(() => useIsAdmin(), { wrapper: wrap({ activeRole: 'admin' }) });
    expect(result.current).toBe(true);
  });
  it('false for null (probe pending, refuse to render admin route)', () => {
    const { result } = renderHook(() => useIsAdmin(), { wrapper: wrap({ activeRole: null }) });
    expect(result.current).toBe(false);
  });
  it('false for member', () => {
    const { result } = renderHook(() => useIsAdmin(), { wrapper: wrap({ activeRole: 'member' }) });
    expect(result.current).toBe(false);
  });
});
