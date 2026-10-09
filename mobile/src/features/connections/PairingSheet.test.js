import { describe, expect, it, vi } from 'vitest';

vi.mock('react-native', () => ({ Share: { share: vi.fn() }, Text: () => null, View: () => null }));
vi.mock('../../components/Sheet', () => ({ Sheet: () => null }));
vi.mock('../../components/Pill', () => ({ Pill: () => null }));
vi.mock('../../components/Row', () => ({ Row: () => null, RowSeparator: () => null }));
vi.mock('../../components/PickerRow', () => ({ PickerRow: () => null }));
vi.mock('../../components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: vi.fn() }) }));
vi.mock('../../lib/clipboard', () => ({ copyText: vi.fn() }));
vi.mock('../../theme/ThemeContext', () => ({ useTheme: () => ({ colors: {}, fonts: {}, fontSizes: {} }) }));

import { liveLink } from './PairingSheet';

describe('pairing link lifetime', () => {
  it('shows the link only while the grant is pending', () => {
    const link = 'alpi://device?url=ws%3A%2F%2F10.0.0.2%3A49200&pairing_token=secret';
    expect(liveLink('pending', link)).toBe(link);
    for (const status of ['consumed', 'expired', 'cancelled']) expect(liveLink(status, link)).toBe('');
  });
});
