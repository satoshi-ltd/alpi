import { beforeEach, describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import * as shared from '../../../common/optimisticProfiles.mjs';
import * as wrapper from './optimisticProfiles';

beforeEach(() => shared._resetProfileEdits());

describe('the mobile wrapper of the shared optimistic store', () => {
  it('re-exports the one store the desktop uses', () => {
    for (const name of Object.keys(shared)) expect(wrapper[name], name).toBe(shared[name]);
  });

  it('re-renders on every edit and overlays it on the roster', () => {
    const { result } = renderHook(() => wrapper.useProfileEdits());
    const before = result.current;
    act(() => {
      wrapper.beginEdit('local', 'doc', { shape: 'heart' });
    });
    expect(result.current).toBeGreaterThan(before);
    expect(wrapper.applyEditsToRows([{ name: 'doc', shape: 'bell' }], 'local')[0].shape).toBe('heart');
  });
});
