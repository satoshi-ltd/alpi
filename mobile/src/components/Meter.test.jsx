import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  flatStyle: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, accessibilityRole, accessibilityValue, ...p }) =>
    React.createElement(
      'div',
      {
        ...p,
        ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
        ...(accessibilityRole ? { role: accessibilityRole } : {}),
        ...(accessibilityValue ? { 'aria-valuenow': accessibilityValue.now } : {}),
        'data-style': JSON.stringify(h.flatStyle(style)),
      },
      children,
    );
  const Text = ({ children, style, ...p }) =>
    React.createElement('span', { ...p, 'data-style': JSON.stringify(h.flatStyle(style)) }, children);
  return { View, Text };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink2: '#333', ink3: '#666', line2: '#ddd', accent: '#c90' },
    fonts: { mono: 'mono' },
    fontSizes: { xs: 11 },
  }),
}));

import { clampFraction, Meter } from './Meter';

function track() {
  return screen.getByRole('progressbar');
}

function fillStyle() {
  return JSON.parse(track().firstChild.getAttribute('data-style'));
}

describe('clampFraction', () => {
  it('passes a fraction through untouched', () => {
    expect(clampFraction(0.42)).toBe(0.42);
  });

  it('clamps below zero and above one', () => {
    expect(clampFraction(-3)).toBe(0);
    expect(clampFraction(4)).toBe(1);
  });

  it('treats a missing or unusable value as empty', () => {
    expect(clampFraction(undefined)).toBe(0);
    expect(clampFraction(NaN)).toBe(0);
    expect(clampFraction(0 / 0)).toBe(0);
  });
});

describe('Meter fill', () => {
  it('draws the bar proportional to the fraction', () => {
    render(<Meter label="Context window" value="12K" tail="/200K" pct={0.06} color="#abc123" />);
    expect(fillStyle().width).toBe('6%');
    expect(fillStyle().backgroundColor).toBe('#abc123');
    expect(screen.getByText('6%')).toBeTruthy();
  });

  it('renders an empty bar at zero', () => {
    render(<Meter label="Daily budget" value="$0.00" tail="/$2.00" pct={0} />);
    expect(fillStyle().width).toBe('0%');
    expect(track().getAttribute('aria-valuenow')).toBe('0');
  });

  it('clamps an overspent bar at full width', () => {
    render(<Meter label="Daily budget" value="$4.00" tail="/$2.00" pct={2} />);
    expect(fillStyle().width).toBe('100%');
    expect(track().getAttribute('aria-valuenow')).toBe('100');
    expect(screen.getByText('100%')).toBeTruthy();
  });

  it('clamps a negative fraction to empty', () => {
    render(<Meter label="Context window" value="0" tail="/200K" pct={-0.5} />);
    expect(fillStyle().width).toBe('0%');
  });

  it('keeps the numeric fraction readable next to the bar', () => {
    render(<Meter label="Context window" value="12K" tail="/200K" pct={0.06} />);
    expect(screen.getByText('12K')).toBeTruthy();
    expect(screen.getByText('/200K')).toBeTruthy();
    expect(track().getAttribute('aria-label')).toBe('Context window');
  });

  it('drops the percent caption when asked', () => {
    render(<Meter label="Context window" value="12K" pct={0.5} showPercent={false} />);
    expect(screen.queryByText('50%')).toBeNull();
    expect(fillStyle().width).toBe('50%');
  });
});
