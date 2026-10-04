import React from 'react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  View: ({ children, style, ...p }) =>
    React.createElement('div', style?.opacity != null ? { ...p, 'data-opacity': String(style.opacity) } : p, children),
  Pressable: ({ children, onPress, style, hitSlop, accessibilityLabel, accessibilityRole, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, ...p }, children),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children, style, edges, ...p }) => React.createElement('div', p, children),
}));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { bg: '#fff', line2: 'rgba(20,20,20,0.14)', accent: '#c90', ink2: '#333', selected: '#eee' } }),
}));

vi.mock('../../components/Fold', () => ({
  Fold: ({ fold, color, size }) => React.createElement('span', { 'data-mark': fold, 'data-color': color ?? '', 'data-size': size }),
}));

vi.mock('../../components/Icon', () => ({
  Icon: ({ name }) => React.createElement('i', { 'data-icon': name }),
}));

import { fireEvent, screen } from '@testing-library/react';
import { PaneContext } from '../../nav/PaneContext';
import { HomePane } from './HomePane';

function pane(value, ui) {
  return render(React.createElement(PaneContext.Provider, { value }, ui));
}

describe('HomePane', () => {
  it('holds the detail pane with a silent mark — nothing to resume says nothing', () => {
    const { container } = render(<HomePane />);
    expect(container.querySelectorAll('[data-mark]')).toHaveLength(1);
    expect(container.textContent).toBe('');
  });

  it('draws the alpaca fold so it takes the brand ink of the theme', () => {
    const { container } = render(<HomePane />);
    const mark = container.querySelector('[data-mark]');
    expect(mark.getAttribute('data-mark')).toBe('alpaca');
    expect(mark.getAttribute('data-color')).toBe('');
    expect(mark.getAttribute('data-size')).toBe('96');
  });

  it('keeps the watermark quiet through opacity rather than a grey tint', () => {
    const { container } = render(<HomePane />);
    const wrapper = container.querySelector('[data-mark]').parentElement;
    expect(Number(wrapper.getAttribute('data-opacity'))).toBeLessThan(0.5);
  });
});

describe('HomePane with a hidden roster', () => {
  it('offers the only way back to the roster when the sidebar is hidden on the root route', () => {
    const toggleSidebar = vi.fn();
    pane({ twoPane: true, side: 'detail', sidebarOpen: false, toggleSidebar }, <HomePane />);
    fireEvent.click(screen.getByRole('button', { name: 'Show sidebar' }));
    expect(toggleSidebar).toHaveBeenCalledTimes(1);
  });

  it('stays silent while the roster is visible or on a phone', () => {
    pane({ twoPane: true, side: 'detail', sidebarOpen: true, toggleSidebar() {} }, <HomePane />);
    expect(screen.queryByRole('button')).toBeNull();
    cleanup();
    pane({ twoPane: false, side: 'full', sidebarOpen: false, toggleSidebar() {} }, <HomePane />);
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('HomePane is a state, not a launcher', () => {
  const source = readFileSync(join(import.meta.dirname, 'HomePane.jsx'), 'utf8');

  it.each(['Composer', 'useChatSend', 'useProfileSummaries', 'useRouter'])(
    'never reaches for %s again — arrival resumes the newest subject instead',
    (symbol) => {
      expect(source).not.toMatch(new RegExp(symbol));
    },
  );
});
