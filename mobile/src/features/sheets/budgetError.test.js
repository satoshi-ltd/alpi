import { describe, expect, it, vi } from 'vitest';

vi.mock('react-native', () => ({ Alert: {}, Pressable: () => null, ScrollView: () => null, Text: () => null, View: () => null }));
vi.mock('../../components/Field', () => ({ Field: () => null }));
vi.mock('../../components/PickerRow', () => ({ PickerRow: () => null }));
vi.mock('../../components/Pill', () => ({ Pill: () => null }));
vi.mock('../../components/Row', () => ({ RowSeparator: () => null, SectionHeader: () => null }));
vi.mock('../../components/Sheet', () => ({ Sheet: () => null }));
vi.mock('../../components/Toast', () => ({ useToast: () => () => {} }));
vi.mock('../../hooks/useDaemonData', () => ({ useOllamaModels: () => ({}) }));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: async () => {} }) }));
vi.mock('../../lib/voicePreview', () => ({ currentlyPlayingVoice: () => null, playVoicePreview: async () => {}, stopVoicePreview: () => {}, subscribeVoicePreview: () => () => {} }));
vi.mock('../../theme/ThemeContext', () => ({ useTheme: () => ({ colors: {}, fonts: {}, fontSizes: {} }) }));

import { budgetError } from './ProfileFieldSheets';
import { renderToStaticMarkup } from 'react-dom/server';
import React from 'react';
import { BudgetSheet } from './ProfileFieldSheets';

describe('budgetError', () => {
  it('accepts a non-negative number or an empty field, rejects everything else', () => {
    expect(budgetError('')).toBeNull();
    expect(budgetError('  ')).toBeNull();
    expect(budgetError('0')).toBeNull();
    expect(budgetError('12.5')).toBeNull();
    expect(budgetError('abc')).toMatch(/number/);
    expect(budgetError('-1')).toMatch(/number/);
  });

  it('mounts with a numeric cap without crashing on the first render', () => {
    expect(() => renderToStaticMarkup(React.createElement(BudgetSheet, { open: true, onClose() {}, profileName: 'doc', initialValue: 1, onSave() {} }))).not.toThrow();
  });
});
