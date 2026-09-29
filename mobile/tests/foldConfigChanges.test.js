import { describe, expect, it } from 'vitest';

import { addFoldConfigChanges, FOLD_CONFIG_CHANGES } from '../plugins/withFoldConfigChanges.js';

function manifest(configChanges) {
  return {
    manifest: {
      application: [
        {
          activity: [
            { $: { 'android:name': '.MainActivity', 'android:configChanges': configChanges } },
            { $: { 'android:name': 'com.facebook.react.devsupport.DevSettingsActivity' } },
          ],
        },
      ],
    },
  };
}

describe('withFoldConfigChanges', () => {
  it('adds density and the size flags a fold flips, keeping what Expo already declares', () => {
    const out = addFoldConfigChanges(manifest('keyboard|keyboardHidden|orientation|screenSize|screenLayout|uiMode'));
    const flags = out.manifest.application[0].activity[0].$['android:configChanges'].split('|');
    expect(flags.slice(0, 6)).toEqual(['keyboard', 'keyboardHidden', 'orientation', 'screenSize', 'screenLayout', 'uiMode']);
    for (const flag of FOLD_CONFIG_CHANGES) expect(flags).toContain(flag);
    expect(new Set(flags).size).toBe(flags.length);
  });

  it('leaves every other activity alone', () => {
    const out = addFoldConfigChanges(manifest('orientation'));
    expect(out.manifest.application[0].activity[1].$['android:configChanges']).toBeUndefined();
  });

  it('is idempotent across repeated prebuilds', () => {
    const once = addFoldConfigChanges(manifest('orientation'));
    const value = once.manifest.application[0].activity[0].$['android:configChanges'];
    const twice = addFoldConfigChanges(once);
    expect(twice.manifest.application[0].activity[0].$['android:configChanges']).toBe(value);
  });

  it('tolerates a manifest without an application block', () => {
    expect(addFoldConfigChanges({ manifest: {} })).toEqual({ manifest: {} });
  });
});
