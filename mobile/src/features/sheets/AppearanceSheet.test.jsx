import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { ACCENTS } from '../../../../common/accents.mjs';
import { FOLD_IDS } from '../../../../common/folds.mjs';

afterEach(cleanup);

const h = vi.hoisted(() => ({ toast: vi.fn() }));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, style, accessibilityLabel, accessibilityRole, accessibilityState, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        'aria-label': accessibilityLabel,
        'aria-pressed': accessibilityState ? String(!!accessibilityState.selected) : undefined,
        'data-width': style && style.width,
        ...p,
      },
      children,
    );
  const Animated = {
    Value: class {},
    timing: () => ({}),
    sequence: () => ({}),
    loop: () => ({ start: () => {}, stop: () => {} }),
    View,
  };
  return {
    Animated,
    Easing: { inOut: (fn) => fn, ease: 'ease' },
    Pressable,
    ScrollView: View,
    Text,
    View,
  };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bgPane: '#ffffff', line2: '#dddddd', ink: '#0b1117', ink2: '#3d4955', ink3: '#7c8896' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'mm' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));

vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, subtitle, primaryAction, children }) =>
    open ? (
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
        {children}
        <button type="button" onClick={primaryAction.onPress} disabled={primaryAction.disabled}>
          {primaryAction.label}
        </button>
      </div>
    ) : null,
}));

vi.mock('../../components/Field', () => ({
  Field: ({ label, value, onChangeText, error }) => (
    <label>
      {label}
      <input aria-label={label} value={value} onChange={(e) => onChangeText(e.target.value)} />
      {error ? <em>{error}</em> : null}
    </label>
  ),
}));

vi.mock('../../components/Toast', () => ({ useToast: () => h.toast }));

const { AppearanceSheet } = await import('./AppearanceSheet');

const mount = (props = {}) => {
  const onSave = vi.fn(async () => {});
  const onClose = vi.fn();
  render(
    <AppearanceSheet
      open
      onClose={onClose}
      profileName="doc"
      initialValue="#3899e2"
      initialFold="shield"
      onSave={onSave}
      {...props}
    />,
  );
  return { onSave, onClose };
};

const save = () => fireEvent.click(screen.getByText('Save appearance'));

beforeEach(() => h.toast.mockReset());

describe('AppearanceSheet', () => {
  it('lays the colours out like the objects, six to a row', () => {
    mount();
    const cell = (label) => screen.getByLabelText(label).getAttribute('data-width');
    expect(cell('shield')).toBeTruthy();
    expect(cell('blue')).toBe(cell('shield'));
    expect(cell('blue')).toBe(`${100 / 6}%`);
  });

  it('offers the twelve objects and the twelve colours', () => {
    mount();
    for (const id of FOLD_IDS) expect(screen.getByLabelText(id)).toBeTruthy();
    for (const [name] of ACCENTS) expect(screen.getByLabelText(name)).toBeTruthy();
    expect(FOLD_IDS).toHaveLength(12);
    expect(ACCENTS).toHaveLength(12);
    expect(document.querySelectorAll('button[aria-label][aria-pressed] svg[data-fold]')).toHaveLength(12);
  });

  it('marks the stored object and colour as selected and names the pair', () => {
    mount();
    expect(screen.getByLabelText('shield').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByLabelText('house').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByLabelText('blue').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('Blue shield')).toBeTruthy();
    expect(screen.getByText('fold: shield · accent: #3899e2')).toBeTruthy();
  });

  it('selects the nearest swatch for an old stored colour', () => {
    mount({ initialValue: '#3a9be0', initialFold: undefined });
    expect(screen.getByLabelText('blue').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByLabelText('amber').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByLabelText('diamond').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('Blue diamond')).toBeTruthy();
  });

  it('saves only the object when only the object changed', async () => {
    const { onSave, onClose } = mount();
    fireEvent.click(screen.getByLabelText('rocket'));
    expect(screen.getByText('Blue rocket')).toBeTruthy();
    save();
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onSave).toHaveBeenCalledWith({ fold: 'rocket' });
  });

  it('saves only the colour when only the colour changed', async () => {
    const { onSave, onClose } = mount();
    fireEvent.click(screen.getByLabelText('teal'));
    save();
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onSave).toHaveBeenCalledWith({ accent: '#2cb3b5' });
  });

  it('saves both when both changed', async () => {
    const { onSave } = mount();
    fireEvent.click(screen.getByLabelText('crown'));
    fireEvent.click(screen.getByLabelText('violet'));
    save();
    await waitFor(() => expect(onSave).toHaveBeenCalledWith({ fold: 'crown', accent: '#9b5ad9' }));
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Appearance saved' }));
  });

  it('resets the object to the diamond and saves it', async () => {
    const { onSave } = mount();
    fireEvent.click(screen.getByLabelText('Reset to diamond'));
    expect(screen.getByLabelText('diamond').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('Blue diamond')).toBeTruthy();
    save();
    await waitFor(() => expect(onSave).toHaveBeenCalledWith({ fold: 'diamond' }));
  });

  it('closes without saving when nothing changed', () => {
    const { onSave, onClose } = mount();
    save();
    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('keeps the sheet open and reports a failed save', async () => {
    const onSave = vi.fn(async () => {
      throw new Error('boom');
    });
    const { onClose } = mount({ onSave });
    fireEvent.click(screen.getByLabelText('tree'));
    save();
    await waitFor(() => expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Save failed' })));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('blocks saving an invalid custom hex', () => {
    const { onSave } = mount();
    fireEvent.change(screen.getByLabelText('Custom hex'), { target: { value: '#12' } });
    expect(screen.getByText('Use a 6-digit #hex colour')).toBeTruthy();
    expect(screen.getByText('Save appearance').disabled).toBe(true);
    save();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('saves a custom hex lower-cased', async () => {
    const { onSave } = mount();
    fireEvent.change(screen.getByLabelText('Custom hex'), { target: { value: '#ABCDEF' } });
    save();
    await waitFor(() => expect(onSave).toHaveBeenCalledWith({ accent: '#abcdef' }));
  });
});
