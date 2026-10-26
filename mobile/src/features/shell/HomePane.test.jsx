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

vi.mock('../../components/EmptyState', () => ({
  EmptyState: ({ mark, title, detail, action }) =>
    React.createElement('div', null, mark, React.createElement('h1', null, title), React.createElement('p', null, detail), action ? React.createElement('button', { type: 'button', onClick: action.onPress }, action.label) : null),
}));
vi.mock('../sheets/CreateProfileSheet', () => ({ CreateProfileSheet: ({ open }) => React.createElement('div', { 'data-create': String(open) }) }));
const role = vi.hoisted(() => ({ admin: true }));
vi.mock('../../hooks/useActiveRole', () => ({ useIsAdmin: () => role.admin }));
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
  it('says what to do with nothing selected and keeps the quiet mark', () => {
    const { container } = render(<HomePane />);
    expect(container.querySelectorAll('[data-mark]')).toHaveLength(1);
    expect(screen.getByText('Pick a profile or a workgroup')).toBeTruthy();
    expect(screen.getByText('Their chats open here.')).toBeTruthy();
  });

  it('offers New profile to an admin and opens the create sheet', () => {
    role.admin = true;
    const { container } = render(<HomePane />);
    expect(container.querySelector('[data-create]').getAttribute('data-create')).toBe('false');
    fireEvent.click(screen.getByRole('button', { name: 'New profile' }));
    expect(container.querySelector('[data-create]').getAttribute('data-create')).toBe('true');
  });

  it('offers a member no way to create', () => {
    role.admin = false;
    try {
      render(<HomePane />);
      expect(screen.queryByRole('button', { name: 'New profile' })).toBeNull();
    } finally {
      role.admin = true;
    }
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
    expect(screen.queryByRole('button', { name: 'Show sidebar' })).toBeNull();
    cleanup();
    pane({ twoPane: false, side: 'full', sidebarOpen: false, toggleSidebar() {} }, <HomePane />);
    expect(screen.queryByRole('button', { name: 'Show sidebar' })).toBeNull();
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
