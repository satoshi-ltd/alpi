import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';

const h = vi.hoisted(() => ({ sessions: { data: null, loading: false } }));

vi.mock('react-native', () => {
  const View = ({ children, ...props }) => React.createElement('div', props, children);
  const Text = ({ children, ...props }) => React.createElement('span', props, children);
  return { View, Text, ScrollView: View };
});
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, subtitle, primaryAction, children }) =>
    open ? (
      <section>
        <h1>{title}</h1>
        <p>{subtitle}</p>
        <button type="button" onClick={primaryAction?.onPress}>{primaryAction?.label}</button>
        {children}
      </section>
    ) : null,
}));
vi.mock('../../components/PickerRow', () => ({
  PickerRow: ({ label, helper, onPress }) => (
    <button type="button" onClick={onPress}>
      <span>{label}</span>
      {helper}
    </button>
  ),
}));
vi.mock('../../components/Row', () => ({
  Row: ({ label, helper }) => (
    <div>
      <span>{label}</span>
      <small>{helper}</small>
    </div>
  ),
  RowSeparator: () => <hr />,
  SectionHeader: ({ children }) => <h2>{children}</h2>,
}));
vi.mock('./SessionsSkeleton', () => ({
  SessionsSkeleton: () => <div data-testid="skeleton" />,
}));
vi.mock('../../hooks/useDaemonData', () => ({
  useSessionsList: () => h.sessions,
}));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink3: '#666', ink4: '#999' },
    fonts: { sans: { regular: 'x', semibold: 'x' }, mono: 'x' },
    fontSizes: { xs: 11, sm: 12, md: 14 },
  }),
}));

import { SessionsSheet } from './SessionsSheet';

const NOW = Date.now() / 1000;

describe('SessionsSheet vocabulary', () => {
  it('calls the thread a session in the title, count and action', () => {
    h.sessions = {
      loading: false,
      data: {
        sessions: [
          { id: 's1', kind: 'chat', first_user: 'ship the release', updated_at: NOW, turn_count: 4 },
          { id: 's2', kind: 'chat', first_user: 'review the diff', updated_at: NOW, turn_count: 1 },
        ],
      },
    };
    const { container } = render(
      <SessionsSheet open onClose={() => {}} profile="doc" activeSessionId="s1" />,
    );
    const scope = within(container);

    expect(scope.getByRole('heading', { level: 1 }).textContent).toBe('Sessions');
    expect(scope.getByText('@doc · 2 sessions')).toBeTruthy();
    expect(scope.getByText('+ New session')).toBeTruthy();
    expect(container.textContent).not.toMatch(/chat/i);
  });

  it('keeps the empty state on session too', () => {
    h.sessions = { loading: false, data: { sessions: [] } };
    const { container } = render(<SessionsSheet open onClose={() => {}} profile="doc" />);

    expect(screen.getByText('No previous sessions')).toBeTruthy();
    expect(container.textContent).not.toMatch(/chat/i);
  });
});
