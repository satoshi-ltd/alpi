import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

vi.mock('../../components/useSheetGesture', () => ({ DURATION_OUT: 220, UNMOUNT_BUFFER: 40 }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../components/ActionSheet', () => ({
  ActionSheet: ({ open, actions, onClose }) =>
    open
      ? React.createElement(
          'div',
          { 'data-chooser': 'true' },
          actions.map((a) => React.createElement('button', { key: a.id, type: 'button', 'data-detail': a.detail, onClick: () => { onClose(); a.onPress(); } }, a.label)),
        )
      : null,
}));
vi.mock('../sheets/ProfileFieldSheets', () => ({
  ModelSheet: ({ open, initialValue, profileModels, onSave }) =>
    open
      ? React.createElement('button', { type: 'button', 'data-model-sheet': initialValue, 'data-models': profileModels.join(','), onClick: () => onSave('openai/gpt-5') }, 'pick model')
      : null,
  ReasoningEffortSheet: ({ open, initialValue, onSave, onClose }) =>
    React.createElement('div', { 'data-effort-mounted': 'true' },
      open ? React.createElement('button', { type: 'button', 'data-effort-sheet': initialValue, onClick: () => { onSave('low'); onClose(); } }, 'pick effort') : null),
}));

import { modelChipLabel } from './modelChip';
import { ModelEffortSheets } from './ModelEffortSheets';

const PROFILE = { name: 'doc', model: 'anthropic/claude-opus-5', model_reasoning_effort: 'medium', models: ['anthropic/claude-opus-5', 'openai/gpt-5'] };

function Host({ onSave }) {
  const [open, setOpen] = React.useState(true);
  return <ModelEffortSheets open={open} onClose={() => setOpen(false)} profile={PROFILE} onSave={onSave} />;
}

describe('ModelEffortSheets', () => {
  it('lists the current model and effort, then opens the model picker after the menu has gone', () => {
    vi.useFakeTimers();
    const onSave = vi.fn();
    render(<Host onSave={onSave} />);
    expect(screen.getByText('Model').getAttribute('data-detail')).toBe('claude-opus-5');
    expect(screen.getByText('Reasoning effort').getAttribute('data-detail')).toBe('medium');
    fireEvent.click(screen.getByText('Model'));
    expect(document.querySelector('[data-model-sheet]')).toBeNull();
    act(() => { vi.advanceTimersByTime(260); });
    const sheet = document.querySelector('[data-model-sheet]');
    expect(sheet.getAttribute('data-model-sheet')).toBe('anthropic/claude-opus-5');
    expect(sheet.getAttribute('data-models')).toBe('anthropic/claude-opus-5,openai/gpt-5');
    fireEvent.click(sheet);
    expect(onSave).toHaveBeenCalledWith('model', 'openai/gpt-5');
  });

  it('saves effort through the same key the settings screen writes', () => {
    vi.useFakeTimers();
    const onSave = vi.fn();
    render(<Host onSave={onSave} />);
    fireEvent.click(screen.getByText('Reasoning effort'));
    act(() => { vi.advanceTimersByTime(260); });
    expect(document.querySelector('[data-effort-sheet]').getAttribute('data-effort-sheet')).toBe('medium');
    fireEvent.click(screen.getByText('pick effort'));
    expect(onSave).toHaveBeenCalledWith('model_reasoning.effort', 'low');
    expect(document.querySelector('[data-effort-mounted]')).toBeTruthy();
    act(() => { vi.advanceTimersByTime(260); });
    expect(document.querySelector('[data-effort-mounted]')).toBeNull();
  });
});

describe('modelChipLabel', () => {
  it('reads model · effort, and the bare model when effort is the provider default', () => {
    expect(modelChipLabel('anthropic/claude-sonnet-4', 'medium')).toBe('claude-sonnet-4 · medium');
    expect(modelChipLabel('anthropic/claude-sonnet-4', '')).toBe('claude-sonnet-4');
    expect(modelChipLabel('', 'high')).toBe('');
  });
});
