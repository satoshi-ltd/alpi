import { describe, expect, it, vi } from 'vitest';

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { addFoldConfigChanges, addOrientationPolicy, FOLD_CONFIG_CHANGES, patchMainActivity, PHONE_MAX_SW_DP } from '../plugins/withFoldConfigChanges.js';
import { MIN_W } from '../src/lib/panes.js';

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

const MAIN_ACTIVITY = `package com.satoshilimited.alpi

import android.os.Bundle
import com.facebook.react.ReactActivity

class MainActivity : ReactActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    SplashScreenManager.registerOnActivity(this)
    super.onCreate(null)
  }
}
`;

describe('phone portrait, tablet rotation', () => {
  const app = JSON.parse(readFileSync(join(import.meta.dirname, '..', 'app.json'), 'utf8')).expo;

  it('lets the app rotate and pins iPhones to portrait while iPads keep all four orientations', () => {
    expect(app.orientation).toBe('default');
    expect(app.ios.supportsTablet).toBe(true);
    expect(app.ios.requireFullScreen).toBe(false);
    expect(app.ios.infoPlist.UISupportedInterfaceOrientations).toEqual(['UIInterfaceOrientationPortrait']);
    expect(app.ios.infoPlist['UISupportedInterfaceOrientations~ipad'].sort()).toEqual([
      'UIInterfaceOrientationLandscapeLeft',
      'UIInterfaceOrientationLandscapeRight',
      'UIInterfaceOrientationPortrait',
      'UIInterfaceOrientationPortraitUpsideDown',
    ]);
  });

  it('locks a phone-sized Android screen to portrait before the first frame and again on every fold', () => {
    const out = addOrientationPolicy(MAIN_ACTIVITY);
    expect(out).toContain(`config.smallestScreenWidthDp < ${PHONE_MAX_SW_DP}`);
    expect(out.indexOf('applyOrientationPolicy(resources.configuration)')).toBeLessThan(out.indexOf('super.onCreate(null)'));
    expect(out).toMatch(/override fun onConfigurationChanged\(newConfig: android\.content\.res\.Configuration\) \{\n\s+super\.onConfigurationChanged\(newConfig\)\n\s+applyOrientationPolicy\(newConfig\)/);
  });

  it('draws the phone line where the roster splits into two panes', () => {
    expect(PHONE_MAX_SW_DP).toBe(MIN_W);
  });

  it('is idempotent and leaves an unrecognised activity untouched', () => {
    const once = addOrientationPolicy(MAIN_ACTIVITY);
    expect(addOrientationPolicy(once)).toBe(once);
    expect(addOrientationPolicy('class Other {}')).toBe('class Other {}');
  });
});

describe('against the Expo 55 MainActivity template', () => {
  const template = readFileSync(join(import.meta.dirname, 'fixtures', 'MainActivity.expo55.kt'), 'utf8');

  it('patches the real prebuild output: policy before super.onCreate, after the splash registration', () => {
    const warn = vi.fn();
    const out = patchMainActivity({ language: 'kt', contents: template }, warn).contents;
    expect(warn).not.toHaveBeenCalled();
    const policy = out.indexOf('applyOrientationPolicy(resources.configuration)');
    expect(policy).toBeGreaterThan(out.indexOf('SplashScreenManager.registerOnActivity(this)'));
    expect(policy).toBeLessThan(out.indexOf('super.onCreate(null)'));
    expect(out).toContain('override fun onConfigurationChanged');
    expect(out).toContain('override fun createReactActivityDelegate');
  });

  it('warns instead of silently shipping rotating phones when the template drifts', () => {
    const warn = vi.fn();
    const drifted = template.replace('super.onCreate(null)', 'super.onCreate(savedInstanceState, true)').replace(/super\.onCreate\(/g, 'super.create(');
    const out = patchMainActivity({ language: 'kt', contents: drifted }, warn);
    expect(out.contents).toBe(drifted);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][0]).toMatch(/no longer matches/);
  });

  it('warns on a Java MainActivity', () => {
    const warn = vi.fn();
    const activity = { language: 'java', contents: 'class MainActivity {}' };
    expect(patchMainActivity(activity, warn)).toBe(activity);
    expect(warn.mock.calls[0][0]).toMatch(/not Kotlin/);
  });
});
