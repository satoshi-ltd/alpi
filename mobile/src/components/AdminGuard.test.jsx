import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ role: null, back: vi.fn() }));

vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('./ScreenHeader', () => ({ ScreenHeader: ({ title, onBack }) => React.createElement('header', {}, React.createElement('button', { type: 'button', onClick: onBack }, 'back'), title) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { bg: '#fff' } }) }));
vi.mock('./Busy', () => ({ Busy: ({ label }) => React.createElement('div', { role: 'progressbar', 'aria-label': label }) }));
vi.mock('../hooks/useActiveRole', () => ({ useActiveRole: () => h.role }));
vi.mock('../hooks/useBack', () => ({ useBack: () => h.back }));

import { AdminGuard } from './AdminGuard';

beforeEach(() => {
  h.role = null;
  h.back.mockClear();
});

describe('AdminGuard', () => {
  it('shows what it is waiting for while the role is unknown, never a blank screen', () => {
    render(<AdminGuard><p>secret</p></AdminGuard>);
    expect(screen.getByRole('progressbar').getAttribute('aria-label')).toBe('Checking access');
    expect(screen.queryByText('secret')).toBeNull();
  });

  it('keeps a way back on screen while the role stays unknown', () => {
    render(<AdminGuard><p>secret</p></AdminGuard>);
    fireEvent.click(screen.getByText('back'));
    expect(h.back).toHaveBeenCalledTimes(1);
  });

  it('renders the page for an admin and nothing for a member, who is sent back', () => {
    h.role = 'admin';
    const admin = render(<AdminGuard><p>secret</p></AdminGuard>);
    expect(screen.getByText('secret')).toBeTruthy();
    admin.unmount();
    h.role = 'member';
    render(<AdminGuard><p>secret</p></AdminGuard>);
    expect(screen.queryByText('secret')).toBeNull();
    expect(screen.queryByRole('progressbar')).toBeNull();
    expect(h.back).toHaveBeenCalledTimes(1);
  });
});
