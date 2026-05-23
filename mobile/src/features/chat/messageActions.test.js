import { describe, it, expect, vi } from 'vitest';

import { buildMessageActions, retryTextFor } from './messageActions.js';

describe('buildMessageActions', () => {
  it('returns empty when no target', () => {
    expect(buildMessageActions(null, { onCopy: vi.fn() })).toEqual([]);
  });

  it('chat user message → Copy + Edit + Retry', () => {
    const target = { kind: 'user', text: 'haz un resumen', turnIndex: 4 };
    const ids = buildMessageActions(target, {
      onCopy: vi.fn(), onEdit: vi.fn(), onRetry: vi.fn(),
    }).map((a) => a.id);
    expect(ids).toEqual(['copy', 'edit', 'retry']);
  });

  it('chat assistant with retryText → Copy + Ask again', () => {
    const target = {
      kind: 'agent',
      text: 'Aquí tienes el resumen…',
      retryText: 'haz un resumen',
      turnIndex: 4,
    };
    const ids = buildMessageActions(target, {
      onCopy: vi.fn(), onEdit: vi.fn(), onRetry: vi.fn(),
    }).map((a) => a.id);
    expect(ids).toEqual(['copy', 'retry-agent']);
  });

  it('agent without retryText (e.g. a workgroup post from someone else) → only Copy', () => {
    const target = { kind: 'agent', text: 'hola desde otro peer' };
    const ids = buildMessageActions(target, {
      onCopy: vi.fn(), onEdit: vi.fn(), onRetry: vi.fn(),
    }).map((a) => a.id);
    expect(ids).toEqual(['copy']);
  });

  it('user message without onRetry handler → Copy + Edit only', () => {
    const target = { kind: 'user', text: 'hi' };
    const ids = buildMessageActions(target, {
      onCopy: vi.fn(), onEdit: vi.fn(),
    }).map((a) => a.id);
    expect(ids).toEqual(['copy', 'edit']);
  });

  it('forwards the target to each callback when fired', () => {
    const target = { kind: 'user', text: 'hello', turnIndex: 2 };
    const onCopy = vi.fn();
    const onEdit = vi.fn();
    const onRetry = vi.fn();
    const actions = buildMessageActions(target, { onCopy, onEdit, onRetry });
    actions.forEach((a) => a.onPress());
    expect(onCopy).toHaveBeenCalledWith(target);
    expect(onEdit).toHaveBeenCalledWith(target);
    expect(onRetry).toHaveBeenCalledWith(target);
  });
});

describe('retryTextFor', () => {
  it('returns the original user prompt for an assistant target (regression: previously echoed the assistant text)', () => {
    const target = {
      kind: 'agent',
      text: 'Aquí tienes el resumen…',
      retryText: 'haz un resumen',
    };
    expect(retryTextFor(target)).toBe('haz un resumen');
  });

  it('returns the user text for a user-kind target', () => {
    expect(retryTextFor({ kind: 'user', text: 'hello' })).toBe('hello');
  });

  it('returns null for assistant without retryText', () => {
    expect(retryTextFor({ kind: 'agent', text: 'something' })).toBeNull();
  });

  it('returns null for missing target', () => {
    expect(retryTextFor(null)).toBeNull();
  });
});
