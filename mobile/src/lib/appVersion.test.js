import { describe, expect, it } from 'vitest';

import app from '../../app.json';
import pkg from '../../package.json';

describe('native version stays in sync with package.json', () => {
  it('app.json expo.version matches package.json version', () => {
    expect(app.expo.version).toBe(pkg.version);
  });

  it('ios buildNumber and android versionCode move in lockstep', () => {
    expect(Number(app.expo.ios.buildNumber)).toBe(app.expo.android.versionCode);
  });
});
