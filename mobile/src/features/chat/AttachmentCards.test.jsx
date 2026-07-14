import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';

const h = vi.hoisted(() => ({
  call: vi.fn(),
  writeAsStringAsync: vi.fn(async () => {}),
  isAvailableAsync: vi.fn(async () => true),
  shareAsync: vi.fn(async () => {}),
  alert: vi.fn(),
}));

vi.mock('react-native', () => {
  const View = ({ children, ...props }) => React.createElement('div', props, children);
  const Text = ({ children, ...props }) => React.createElement('span', props, children);
  const Pressable = ({ children, onPress, accessibilityLabel, ...props }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, ...props },
      children instanceof Function ? children({ pressed: false }) : children);
  return {
    View,
    Text,
    Pressable,
    Image: (props) => React.createElement('img', props),
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    Alert: { alert: h.alert },
  };
});
vi.mock('expo-file-system/legacy', () => ({
  cacheDirectory: 'file:///cache/',
  EncodingType: { Base64: 'base64' },
  writeAsStringAsync: h.writeAsStringAsync,
}));
vi.mock('expo-sharing', () => ({
  isAvailableAsync: h.isAvailableAsync,
  shareAsync: h.shareAsync,
}));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => <i>{name}</i> }));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call, endpoint: { id: 'c1' } }) }));
vi.mock('../../hooks/useCachedImage', () => ({ useCachedImage: () => ({ uri: null, err: null }) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink3: '#666', hover: '#eee', bgPane: '#fff', line: '#ddd', line2: '#ddd' },
    fonts: { sans: { regular: 'sans' }, mono: 'mono' },
    fontSizes: { xs: 10, sm: 12 },
  }),
}));

import { AttachmentCards } from './AttachmentCards.jsx';

const PDF = {
  name: 'report.pdf',
  mime: 'application/pdf',
  size: 9 * 1024 * 1024,
  path: '/data/.alpi/profiles/agora/out/report.pdf',
};

afterEach(cleanup);

beforeEach(() => {
  h.call.mockReset();
  h.writeAsStringAsync.mockClear();
  h.isAvailableAsync.mockClear();
  h.shareAsync.mockClear();
  h.alert.mockClear();
});

describe('AttachmentCards document share flow', () => {
  it('pressing a document card fetches with the 60s window and hands the file to shareAsync', async () => {
    h.call.mockResolvedValue({ data_base64: 'QUJD', mime: 'application/pdf' });
    render(<AttachmentCards items={[PDF]} variant="message" profile="agora" />);

    fireEvent.click(screen.getByRole('button', { name: 'Open report.pdf' }));

    await waitFor(() => expect(h.shareAsync).toHaveBeenCalled());
    expect(h.call).toHaveBeenCalledWith(
      'host.attachments.fetch',
      { profile: 'agora', path: PDF.path },
      { timeoutMs: 60_000 },
    );
    expect(h.writeAsStringAsync).toHaveBeenCalledWith(
      'file:///cache/report.pdf', 'QUJD', { encoding: 'base64' },
    );
    expect(h.shareAsync).toHaveBeenCalledWith(
      'file:///cache/report.pdf', { mimeType: 'application/pdf', dialogTitle: 'report.pdf' },
    );
    expect(h.alert).not.toHaveBeenCalled();
  });

  it('a failed fetch surfaces the alert instead of sharing', async () => {
    h.call.mockRejectedValue(new Error('request timed out after 60000ms'));
    render(<AttachmentCards items={[PDF]} variant="message" profile="agora" />);

    fireEvent.click(screen.getByRole('button', { name: 'Open report.pdf' }));

    await waitFor(() => expect(h.alert).toHaveBeenCalled());
    expect(h.shareAsync).not.toHaveBeenCalled();
  });
});
