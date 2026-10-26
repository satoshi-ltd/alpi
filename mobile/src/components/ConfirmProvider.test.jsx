import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('./ConfirmDialog', () => ({
  ConfirmDialog: ({ open, title, body, confirmLabel, cancelLabel, alternateLabel, typed, onConfirm, onAlternate, onClose }) =>
    open
      ? React.createElement('div', { 'data-typed': String(typed) },
          React.createElement('h1', null, title),
          React.createElement('p', null, body),
          React.createElement('button', { onClick: onConfirm }, confirmLabel),
          alternateLabel ? React.createElement('button', { onClick: onAlternate }, alternateLabel) : null,
          React.createElement('button', { onClick: onClose }, cancelLabel))
      : null,
}));

import { ConfirmProvider, useConfirm } from './ConfirmProvider';

function setup() {
  const out = { confirm: null };
  const Grab = () => { out.confirm = useConfirm(); return null; };
  render(<ConfirmProvider><Grab /></ConfirmProvider>);
  return out;
}

describe('ConfirmProvider', () => {
  it('resolves true when the primary is pressed and shows no typed field by default', async () => {
    const out = setup();
    let answer;
    act(() => { out.confirm({ title: 'Discard changes?', body: 'Unsaved.', confirmLabel: 'Discard', cancelLabel: 'Keep editing' }).then((v) => { answer = v; }); });
    expect(screen.getByText('Discard changes?')).toBeTruthy();
    fireEvent.click(screen.getByText('Discard'));
    await act(async () => {});
    expect(answer).toBe(true);
    expect(screen.queryByText('Discard changes?')).toBeNull();
  });

  it('resolves alternate when the third action is pressed', async () => {
    const out = setup();
    let answer;
    act(() => { out.confirm({ title: 'Changed elsewhere', body: 'x', confirmLabel: 'Overwrite', alternateLabel: 'Reload (discard)', cancelLabel: 'Keep editing' }).then((v) => { answer = v; }); });
    fireEvent.click(screen.getByText('Reload (discard)'));
    await act(async () => {});
    expect(answer).toBe('alternate');
  });

  it('resolves false on cancel and false for a request it replaces', async () => {
    const out = setup();
    const answers = [];
    act(() => { out.confirm({ title: 'First', body: 'a' }).then((v) => answers.push(['first', v])); });
    act(() => { out.confirm({ title: 'Second', body: 'b', expected: 'x' }).then((v) => answers.push(['second', v])); });
    await act(async () => {});
    expect(answers).toEqual([['first', false]]);
    fireEvent.click(screen.getByText('Cancel'));
    await act(async () => {});
    expect(answers).toEqual([['first', false], ['second', false]]);
  });

  it('asks for the typed word when one is expected', () => {
    const out = setup();
    act(() => { out.confirm({ title: 'Delete', body: 'x', expected: 'roma' }); });
    expect(document.querySelector('[data-typed]').getAttribute('data-typed')).toBe('true');
  });
});
