import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ id: 'galt', roster: { data: null, error: null }, back: vi.fn() }));

vi.mock('expo-router', () => ({ useLocalSearchParams: () => ({ id: h.id }) }));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('./ScreenHeader', () => ({ ScreenHeader: ({ title }) => React.createElement('header', {}, title) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { bg: '#fff' } }) }));
vi.mock('./Busy', () => ({ Busy: ({ label }) => React.createElement('div', { role: 'progressbar', 'aria-label': label }) }));
vi.mock('../hooks/useBack', () => ({ useBack: () => h.back }));
vi.mock('../hooks/useDaemonData', () => ({ useProfileSummaries: () => h.roster }));

import { ProfileGuard } from './ProfileGuard';

const roster = (...names) => ({ data: { profiles: names.map((name) => ({ name })) }, error: null });

beforeEach(() => {
  h.id = 'galt';
  h.roster = { data: null, error: null };
  h.back.mockClear();
});

describe('ProfileGuard', () => {
  it('waits for the roster before the page can ask the daemon about the profile', () => {
    render(<ProfileGuard><p>page</p></ProfileGuard>);
    expect(screen.getByRole('progressbar')).toBeTruthy();
    expect(screen.queryByText('page')).toBeNull();
    expect(h.back).not.toHaveBeenCalled();
  });

  it('renders the page for a profile the connection lists', () => {
    h.roster = roster('alpi', 'galt');
    render(<ProfileGuard><p>page</p></ProfileGuard>);
    expect(screen.getByText('page')).toBeTruthy();
    expect(h.back).not.toHaveBeenCalled();
  });

  it('sends back a profile the connection does not list, without rendering the page', () => {
    h.roster = roster('alpi', 'sentinel');
    render(<ProfileGuard><p>page</p></ProfileGuard>);
    expect(screen.queryByText('page')).toBeNull();
    expect(h.back).toHaveBeenCalledTimes(1);
  });

  it('always accepts the default profile', () => {
    h.id = 'default';
    h.roster = roster('alpi');
    render(<ProfileGuard><p>page</p></ProfileGuard>);
    expect(screen.getByText('page')).toBeTruthy();
  });

  it('lets the page show its own error when the roster cannot be read', () => {
    h.roster = { data: null, error: new Error('offline') };
    render(<ProfileGuard><p>page</p></ProfileGuard>);
    expect(screen.getByText('page')).toBeTruthy();
    expect(h.back).not.toHaveBeenCalled();
  });

  it('wraps every profile screen: the layout puts the guard around the stack, inside the admin guard', () => {
    const layout = readFileSync(join(import.meta.dirname, '../../app/profile/[id]/_layout.jsx'), 'utf8');
    expect(layout).toMatch(/<AdminGuard>\s*<ProfileGuard>\s*<Stack screenOptions=\{screenOptions\} \/>\s*<\/ProfileGuard>\s*<\/AdminGuard>/);
  });
});
