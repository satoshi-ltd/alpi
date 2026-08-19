import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('../src/components/Banner', () => ({
  Banner: ({ kind, children, action, onAction }) =>
    React.createElement(
      'div',
      { 'data-banner': kind },
      children,
      action
        ? React.createElement('button', { type: 'button', 'data-banner-action': action, onClick: onAction })
        : null,
    ),
}));

import { DAEMON_STATUS_BANNERS, DaemonBanner, isDaemonDown } from '../src/components/DaemonBanner';

const SURFACES = [
  'app/index.jsx',
  'app/chat/[id].jsx',
  'app/wg/[id].jsx',
  'src/features/shell/SidebarPane.jsx',
];

const QUIET_STATUSES = new Set(['online', 'connected', 'probing', 'unknown']);

const sourceOf = (rel) => readFileSync(join(import.meta.dirname, '..', rel), 'utf8');

const banner = () => document.querySelector('[data-banner]');

describe('Daemon status mapping', () => {
  it('explains every failure status the probe can report', () => {
    const emitted = [...sourceOf('src/lib/probe.js').matchAll(/status: '([a-z-]+)'/g)].map((m) => m[1]);
    const failures = [...new Set(emitted)].filter((s) => !QUIET_STATUSES.has(s)).sort();
    expect(failures).toEqual(Object.keys(DAEMON_STATUS_BANNERS).sort());
  });

  it('keeps the down predicate and the explained statuses the same set', () => {
    for (const status of Object.keys(DAEMON_STATUS_BANNERS)) expect(isDaemonDown(status)).toBe(true);
    for (const status of QUIET_STATUSES) expect(isDaemonDown(status)).toBe(false);
    expect(isDaemonDown('constructor')).toBe(false);
    expect(isDaemonDown(undefined)).toBe(false);
  });

  it('gives every status a tone and one-sentence-or-more copy', () => {
    for (const [status, entry] of Object.entries(DAEMON_STATUS_BANNERS)) {
      expect(['danger', 'warning', 'info'], status).toContain(entry.kind);
      expect(entry.message.length, status).toBeGreaterThan(10);
    }
  });
});

describe('DaemonBanner', () => {
  it('renders the mapped copy for each down status', () => {
    for (const [status, entry] of Object.entries(DAEMON_STATUS_BANNERS)) {
      render(<DaemonBanner status={status} />);
      expect(banner().getAttribute('data-banner'), status).toBe(entry.kind);
      expect(banner().textContent, status).toContain(entry.message);
      cleanup();
    }
  });

  it('stays silent on a healthy or still-probing daemon', () => {
    for (const status of QUIET_STATUSES) {
      render(<DaemonBanner status={status} />);
      expect(banner(), status).toBeNull();
      cleanup();
    }
  });

  it('stays silent while unpaired even though the status reads offline', () => {
    render(<DaemonBanner status="offline" paired={false} onRetry={vi.fn()} />);
    expect(banner()).toBeNull();
  });

  it('keeps the retry affordance on the status that offered it', () => {
    const onRetry = vi.fn();
    render(<DaemonBanner status="offline" onRetry={onRetry} />);
    const action = document.querySelector('[data-banner-action]');
    expect(action.getAttribute('data-banner-action')).toBe('Retry');
    fireEvent.click(action);
    expect(onRetry).toHaveBeenCalled();
  });

  it('offers no action when the status has no recovery the phone can drive', () => {
    for (const status of ['disabled', 'auth-failed']) {
      render(<DaemonBanner status={status} onRetry={vi.fn()} />);
      expect(document.querySelector('[data-banner-action]'), status).toBeNull();
      cleanup();
    }
  });

  it('drops the action label when the surface passes no retry handler', () => {
    render(<DaemonBanner status="offline" />);
    expect(document.querySelector('[data-banner-action]')).toBeNull();
  });
});

describe('Daemon health has a single source across every surface', () => {
  it('draws the banner from the shared component on all four surfaces', () => {
    for (const rel of SURFACES) {
      const src = sourceOf(rel);
      expect(src, rel).toMatch(/import \{ DaemonBanner, isDaemonDown \} from '[^']*components\/DaemonBanner'/);
      expect(src, rel).toContain('<DaemonBanner');
    }
  });

  it('leaves no surface holding its own copy of the status explanations', () => {
    for (const rel of SURFACES) {
      const src = sourceOf(rel);
      for (const entry of Object.values(DAEMON_STATUS_BANNERS)) {
        expect(src.includes(entry.message), `${rel} inlines "${entry.message}"`).toBe(false);
      }
    }
  });

  it('leaves no surface branching on a status the mapping already owns', () => {
    for (const rel of SURFACES) {
      const src = sourceOf(rel);
      for (const status of Object.keys(DAEMON_STATUS_BANNERS)) {
        expect(src.includes(`=== '${status}'`), `${rel} branches on '${status}'`).toBe(false);
      }
    }
  });
});
