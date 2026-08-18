import { describe, it, expect } from 'vitest';

import { canComposerSend } from './composerSend.js';

describe('canComposerSend', () => {
  it('allows sending text with a valid task shape', () => {
    expect(canComposerSend({ hasText: true, hasAttachments: false, taskOk: true, disabled: false })).toBe(true);
  });

  it('allows sending with only an attachment', () => {
    expect(canComposerSend({ hasText: false, hasAttachments: true, taskOk: true, disabled: false })).toBe(true);
  });

  it('blocks an empty composer', () => {
    expect(canComposerSend({ hasText: false, hasAttachments: false, taskOk: true, disabled: false })).toBe(false);
  });

  it('blocks an invalid task shape', () => {
    expect(canComposerSend({ hasText: true, hasAttachments: false, taskOk: false, disabled: false })).toBe(false);
  });

  it('blocks every send when disabled, even with valid text + attachment (paused profile)', () => {
    expect(canComposerSend({ hasText: true, hasAttachments: true, taskOk: true, disabled: true })).toBe(false);
  });

  it('blocks a second send while the current turn is still streaming', () => {
    expect(canComposerSend({ hasText: true, hasAttachments: false, taskOk: true, disabled: false, busy: true })).toBe(false);
    expect(canComposerSend({ hasText: true, hasAttachments: false, taskOk: true, disabled: false, busy: false })).toBe(true);
  });
});
