import { StrictMode } from 'react';
import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';

import { useReveal } from './useReveal';

const mount = (on, wrapper) => renderHook(({ shown }) => useReveal(shown), { initialProps: { shown: on }, wrapper });

describe('useReveal', () => {
  it('is false for content that never had bones', () => {
    const { result, rerender } = mount(false);
    expect(result.current).toBe(false);
    rerender({ shown: false });
    expect(result.current).toBe(false);
  });

  it('is false while the bones are up and true once they hand over', () => {
    const { result, rerender } = mount(true);
    expect(result.current).toBe(false);
    rerender({ shown: false });
    expect(result.current).toBe(true);
  });

  it('survives StrictMode double renders', () => {
    const { result, rerender } = mount(false, StrictMode);
    expect(result.current).toBe(false);
    rerender({ shown: true });
    rerender({ shown: false });
    expect(result.current).toBe(true);
  });
});
