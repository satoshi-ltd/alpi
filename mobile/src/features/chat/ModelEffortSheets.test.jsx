import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

vi.mock('../../components/useSheetGesture', () => ({ DURATION_OUT: 220, UNMOUNT_BUFFER: 40 }));
vi.mock('../sheets/ProfileFieldSheets', () => ({
  ModelSheet: ({ open, initialValue, profileModels, onSave }) =>
    open
      ? React.createElement('button', { type: 'button', 'data-model-sheet': initialValue, 'data-models': profileModels.join(','), onClick: () => onSave('openai/gpt-5') }, 'pick model')
      : null,
  ReasoningEffortSheet: ({ open, initialValue, onSave, onClose, modelRow }) =>
    open
      ? React.createElement('div', { 'data-effort-sheet': initialValue },
        React.createElement('button', { type: 'button', onClick: () => { onSave('low'); onClose(); } }, 'pick effort'),
        React.createElement('button', { type: 'button', 'data-detail': modelRow.label, onClick: modelRow.onPress }, 'change model'))
      : null,
}));

import { modelChipLabel, modelChipParts } from './modelChip';
import { ModelEffortSheets } from './ModelEffortSheets';

const PROFILE = { name: 'doc', model: 'anthropic/claude-opus-5', model_reasoning_effort: 'medium', models: ['anthropic/claude-opus-5', 'openai/gpt-5'] };

function Host({ onSave }) {
  const [open, setOpen] = React.useState(true);
  return <ModelEffortSheets open={open} onClose={() => setOpen(false)} profile={PROFILE} onSave={onSave} />;
}

describe('ModelEffortSheets', () => {
  it('opens the effort picker directly, with no router sheet in between', () => {
    render(<Host onSave={() => {}} />);
    expect(document.querySelector('[data-effort-sheet]').getAttribute('data-effort-sheet')).toBe('medium');
    expect(screen.queryByText('Reasoning effort')).toBeNull();
  });

  it('saves effort through the same key the settings screen writes', () => {
    const onSave = vi.fn();
    render(<Host onSave={onSave} />);
    fireEvent.click(screen.getByText('pick effort'));
    expect(onSave).toHaveBeenCalledWith('model_reasoning.effort', 'low');
    expect(document.querySelector('[data-effort-sheet]')).toBeNull();
  });

  it('reaches the model list from the picker once it has gone', () => {
    vi.useFakeTimers();
    const onSave = vi.fn();
    render(<Host onSave={onSave} />);
    expect(screen.getByText('change model').getAttribute('data-detail')).toBe('claude-opus-5');
    fireEvent.click(screen.getByText('change model'));
    expect(document.querySelector('[data-model-sheet]')).toBeNull();
    act(() => { vi.advanceTimersByTime(260); });
    const sheet = document.querySelector('[data-model-sheet]');
    expect(sheet.getAttribute('data-model-sheet')).toBe('anthropic/claude-opus-5');
    expect(sheet.getAttribute('data-models')).toBe('anthropic/claude-opus-5,openai/gpt-5');
    fireEvent.click(sheet);
    expect(onSave).toHaveBeenCalledWith('model', 'openai/gpt-5');
  });
});

describe('modelChipLabel', () => {
  it('reads model · effort, and the bare model when effort is the provider default', () => {
    expect(modelChipLabel('anthropic/claude-sonnet-4', 'medium')).toBe('claude-sonnet-4 · medium');
    expect(modelChipLabel('anthropic/claude-sonnet-4', '')).toBe('claude-sonnet-4');
    expect(modelChipLabel('', 'high')).toBe('');
  });
});

describe('modelChipParts', () => {
  it('splits the model from the effort so the label can shrink the model first', () => {
    expect(modelChipParts('anthropic/claude-sonnet-4', ' medium ')).toEqual({ model: 'claude-sonnet-4', effort: 'medium' });
    expect(modelChipParts('anthropic/claude-sonnet-4', null)).toEqual({ model: 'claude-sonnet-4', effort: '' });
    expect(modelChipParts('', 'high')).toBeNull();
  });
});
