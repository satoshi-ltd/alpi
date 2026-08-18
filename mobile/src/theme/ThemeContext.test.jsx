import React from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

afterEach(cleanup);

const h = vi.hoisted(() => ({ store: new Map() }));

vi.mock('react-native', () => ({
  useColorScheme: () => 'light',
}));

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (key) => (h.store.has(key) ? h.store.get(key) : null)),
  setItemAsync: vi.fn(async (key, value) => {
    h.store.set(key, value);
  }),
  deleteItemAsync: vi.fn(async (key) => {
    h.store.delete(key);
  }),
}));

import * as SecureStore from 'expo-secure-store';

import { ThemeProvider, useTheme } from './ThemeContext';
import { MAX_TEXT_SCALE, MIN_TEXT_SCALE } from './textScale';
import { fontSizes as rawFontSizes } from './tokens';

let setScale;

function Probe() {
  const { fontSizes, textScale, setTextScale } = useTheme();
  setScale = setTextScale;
  return (
    <div>
      <span data-testid="md">{fontSizes.md}</span>
      <span data-testid="display">{fontSizes.display}</span>
      <span data-testid="scale">{textScale}</span>
    </div>
  );
}

function mount() {
  return render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>,
  );
}

const read = (id) => Number(screen.getByTestId(id).textContent);

beforeEach(() => {
  h.store.clear();
  setScale = undefined;
  SecureStore.setItemAsync.mockClear();
});

describe('theme text scale', () => {
  it('starts byte-identical to the raw tokens for a user who never touched it', async () => {
    mount();
    await waitFor(() => expect(read('scale')).toBe(1));
    expect(read('md')).toBe(rawFontSizes.md);
    expect(read('display')).toBe(rawFontSizes.display);
  });

  it('re-renders every consumer when the scale changes, with no per-screen wiring', async () => {
    mount();
    await waitFor(() => expect(read('scale')).toBe(1));
    await act(async () => setScale(MAX_TEXT_SCALE));
    expect(read('scale')).toBe(MAX_TEXT_SCALE);
    expect(read('md')).toBeGreaterThan(rawFontSizes.md);
    expect(read('display')).toBeGreaterThan(rawFontSizes.display);
  });

  it('persists the choice under its own key and reloads it on the next launch', async () => {
    mount();
    await waitFor(() => expect(read('scale')).toBe(1));
    await act(async () => setScale(MAX_TEXT_SCALE));
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith('alpi.textScale', String(MAX_TEXT_SCALE));

    cleanup();
    mount();
    await waitFor(() => expect(read('scale')).toBe(MAX_TEXT_SCALE));
    expect(read('md')).toBeGreaterThan(rawFontSizes.md);
  });

  it('clamps a stored out-of-range scale at both ends', async () => {
    h.store.set('alpi.textScale', '9');
    mount();
    await waitFor(() => expect(read('scale')).toBe(MAX_TEXT_SCALE));

    cleanup();
    h.store.set('alpi.textScale', '0.1');
    mount();
    await waitFor(() => expect(read('scale')).toBe(MIN_TEXT_SCALE));
  });

  it('falls back to the default when the stored value is corrupt', async () => {
    h.store.set('alpi.textScale', 'huge');
    mount();
    await waitFor(() => expect(read('md')).toBe(rawFontSizes.md));
    expect(read('scale')).toBe(1);
  });

  it('never writes a value outside the scale, whatever a caller asks for', async () => {
    mount();
    await waitFor(() => expect(read('scale')).toBe(1));
    await act(async () => setScale(42));
    expect(read('scale')).toBe(MAX_TEXT_SCALE);
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith('alpi.textScale', String(MAX_TEXT_SCALE));
  });
});
