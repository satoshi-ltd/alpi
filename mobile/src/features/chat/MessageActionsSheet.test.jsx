import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const h = vi.hoisted(() => ({ copied: [] }));

vi.mock('expo-clipboard', () => ({ setStringAsync: async (t) => { h.copied.push(t); } }));
vi.mock('../../components/useSheetGesture', () => ({ DURATION_OUT: 220, UNMOUNT_BUFFER: 40 }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { ink2: '#333' } }) }));
vi.mock('../../components/ActionSheet', () => ({
  ActionSheet: ({ open, actions, onClose }) =>
    open
      ? React.createElement(
          'div',
          { 'data-actions': 'true' },
          actions.map((a) => React.createElement('button', { key: a.id, type: 'button', onClick: () => { onClose?.(); a.onPress(); } }, a.label)),
        )
      : null,
}));
vi.mock('./SelectTextSheet', () => ({
  SelectTextSheet: ({ text, onClose }) =>
    React.createElement('pre', { 'data-select': text ?? '', 'data-mounted': 'true', onClick: onClose }, text),
}));

import { MessageActionsSheet } from './MessageActionsSheet';

function Host({ target: initial }) {
  const [target, setTarget] = React.useState(initial);
  return <MessageActionsSheet target={target} onClose={() => setTarget(null)} onRetry={() => {}} onEdit={() => {}} />;
}

describe('MessageActionsSheet', () => {
  it('Copy copies the whole message', async () => {
    h.copied.length = 0;
    render(<Host target={{ kind: 'agent', text: 'the whole\nanswer' }} />);
    await act(async () => { fireEvent.click(screen.getByText('Copy')); });
    expect(h.copied).toEqual(['the whole\nanswer']);
  });

  it('Select text opens the message in a selectable view once the menu has gone', () => {
    vi.useFakeTimers();
    render(<Host target={{ kind: 'user', text: 'pick a word' }} />);
    fireEvent.click(screen.getByText('Select text'));
    expect(document.querySelector('[data-actions]')).toBeNull();
    expect(document.querySelector('[data-mounted]')).toBeNull();
    act(() => { vi.advanceTimersByTime(260); });
    expect(document.querySelector('[data-select]').textContent).toBe('pick a word');
  });

  it('unmounts the text view once it has closed', () => {
    vi.useFakeTimers();
    render(<Host target={{ kind: 'user', text: 'pick a word' }} />);
    fireEvent.click(screen.getByText('Select text'));
    act(() => { vi.advanceTimersByTime(260); });
    fireEvent.click(document.querySelector('[data-select]'));
    expect(document.querySelector('[data-select]').getAttribute('data-select')).toBe('');
    act(() => { vi.advanceTimersByTime(260); });
    expect(document.querySelector('[data-mounted]')).toBeNull();
  });
});
