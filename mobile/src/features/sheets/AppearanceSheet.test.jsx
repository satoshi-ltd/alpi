import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { ACCENTS } from '../../../../common/accents.mjs';
import { SHAPE_IDS } from '../../../../common/shapes.mjs';

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
      initialShape="bell"
      onSave={onSave}
      {...props}
    />,
  );
  return { onSave, onClose };
};

const save = () => fireEvent.click(screen.getByText('Save appearance'));

beforeEach(() => h.toast.mockReset());

describe('AppearanceSheet', () => {
  it('lays the colours out like the shapes, six to a row', () => {
    mount();
    const cell = (label) => screen.getByLabelText(label).getAttribute('data-width');
    expect(cell('bell')).toBeTruthy();
    expect(cell('blue')).toBe(cell('bell'));
    expect(cell('blue')).toBe(`${100 / 6}%`);
  });

  it('offers the twelve shapes by name and the twelve colours', () => {
    mount();
    for (const id of SHAPE_IDS) expect(screen.getByLabelText(id)).toBeTruthy();
    expect(new Set(SHAPE_IDS).size).toBe(12);
    expect(screen.getByText('Shape')).toBeTruthy();
    expect(screen.getByText('@doc · shape and colour')).toBeTruthy();
    for (const [name] of ACCENTS) expect(screen.getByLabelText(name)).toBeTruthy();
    expect(SHAPE_IDS).toHaveLength(12);
    expect(ACCENTS).toHaveLength(12);
    expect(document.querySelectorAll('button[aria-label][aria-pressed] svg[data-shape]')).toHaveLength(12);
  });

  it('marks the stored shape and colour as selected and names the pair by the shape it draws', () => {
    mount();
    expect(screen.getByLabelText('bell').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByLabelText('arch').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByLabelText('blue').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('Blue bell')).toBeTruthy();
    expect(screen.getByText('shape: bell · accent: #3899e2')).toBeTruthy();
  });

  it('selects the nearest swatch for an old stored colour', () => {
    mount({ initialValue: '#3a9be0', initialShape: undefined });
    expect(screen.getByLabelText('blue').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByLabelText('amber').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByLabelText('round').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('Blue round')).toBeTruthy();
  });

  it('saves only the shape name when only the shape changed', async () => {
    const { onSave, onClose } = mount();
    fireEvent.click(screen.getByLabelText('pill'));
    expect(screen.getByText('Blue pill')).toBeTruthy();
    save();
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onSave).toHaveBeenCalledWith({ shape: 'pill' });
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
    fireEvent.click(screen.getByLabelText('dome'));
    fireEvent.click(screen.getByLabelText('violet'));
    save();
    await waitFor(() => expect(onSave).toHaveBeenCalledWith({ shape: 'dome', accent: '#9b5ad9' }));
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Appearance saved' }));
  });

  it('resets the shape to round and saves the shape name', async () => {
    const { onSave } = mount();
    fireEvent.click(screen.getByLabelText('Reset to round'));
    expect(screen.getByLabelText('round').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('Blue round')).toBeTruthy();
    save();
    await waitFor(() => expect(onSave).toHaveBeenCalledWith({ shape: 'round' }));
  });

  it('reads a legacy id as the round, never as its old shape, and saves nothing unchanged', () => {
    const { onSave, onClose } = mount({ initialShape: 'shield' });
    expect(screen.getByLabelText('round').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByLabelText('bell').getAttribute('aria-pressed')).toBe('false');
    save();
    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('closes without saving when nothing changed', () => {
    const { onSave, onClose } = mount();
    save();
    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('closes at once without waiting for the daemon and reports a failed save', async () => {
    let fail;
    const onSave = vi.fn(() => new Promise((_, reject) => { fail = reject; }));
    const { onClose } = mount({ onSave });
    fireEvent.click(screen.getByLabelText('pebble'));
    save();
    expect(onSave).toHaveBeenCalledWith({ shape: 'pebble' });
    expect(onClose).toHaveBeenCalled();
    expect(h.toast).not.toHaveBeenCalled();
    fail(new Error('boom'));
    await waitFor(() => expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Save failed' })));
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
