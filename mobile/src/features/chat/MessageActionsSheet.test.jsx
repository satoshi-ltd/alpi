import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const h = vi.hoisted(() => ({
  copied: [],
  toast: vi.fn(),
  shareMarkdown: vi.fn(async () => {}),
  sharePdf: vi.fn(async () => {}),
}));

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
vi.mock('../../components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ activeId: 'c1', connections: [{ id: 'c1', name: 'casa' }] }) }));
vi.mock('../../lib/messageExport', () => ({ shareMarkdown: h.shareMarkdown, sharePdf: h.sharePdf }));
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

  describe('exports', () => {
    const AGENT = {
      kind: 'agent',
      text: 'raw ![img](/tmp/a.png) reply',
      exportBody: 'clean reply',
      exportProfile: 'pulse',
      exportAt: 1792944000,
      exportAccent: '#3fb37a',
    };
    const settle = () => act(async () => { await vi.advanceTimersByTimeAsync(260); });

    it('downloads an agent message as markdown signed with its profile and the active server', async () => {
      vi.useFakeTimers();
      h.shareMarkdown.mockClear();
      render(<Host target={AGENT} />);
      fireEvent.click(screen.getByText('Download .md'));
      expect(h.shareMarkdown).not.toHaveBeenCalled();
      await settle();
      expect(h.shareMarkdown).toHaveBeenCalledWith({ profile: 'pulse', server: 'casa', at: 1792944000, body: 'clean reply' });
    });

    it('exports an agent message to PDF with its accent once the menu has gone', async () => {
      vi.useFakeTimers();
      h.sharePdf.mockClear();
      render(<Host target={AGENT} />);
      fireEvent.click(screen.getByText('Export PDF…'));
      expect(h.sharePdf).not.toHaveBeenCalled();
      await settle();
      expect(h.sharePdf).toHaveBeenCalledWith({ profile: 'pulse', server: 'casa', at: 1792944000, body: 'clean reply' }, '#3fb37a');
    });

    it('falls back to the message text and names the default profile alpi', async () => {
      vi.useFakeTimers();
      h.shareMarkdown.mockClear();
      render(<Host target={{ kind: 'agent', text: 'hello', exportProfile: 'default' }} />);
      fireEvent.click(screen.getByText('Download .md'));
      await settle();
      expect(h.shareMarkdown).toHaveBeenCalledWith({ profile: 'alpi', server: 'casa', at: 0, body: 'hello' });
    });

    it('says why an export failed', async () => {
      vi.useFakeTimers();
      h.toast.mockClear();
      h.sharePdf.mockRejectedValueOnce(new Error('no printer'));
      render(<Host target={AGENT} />);
      fireEvent.click(screen.getByText('Export PDF…'));
      await settle();
      expect(h.toast).toHaveBeenCalledWith({ message: 'Export failed: no printer', kind: 'danger' });
    });

    it('offers no exports on your own message', () => {
      render(<Host target={{ kind: 'user', text: 'hi' }} />);
      expect(screen.queryByText('Download .md')).toBeNull();
      expect(screen.queryByText('Export PDF…')).toBeNull();
    });
  });
});
