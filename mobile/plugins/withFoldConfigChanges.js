const { WarningAggregator, withAndroidManifest, withMainActivity } = require('expo/config-plugins');

// A foldable's inner and cover screens differ in density; without these flags Android recreates the activity on every fold and the JS app restarts.
const FOLD_CONFIG_CHANGES = ['density', 'smallestScreenSize', 'screenSize', 'screenLayout', 'orientation'];

function addFoldConfigChanges(manifest) {
  const application = manifest?.manifest?.application?.[0];
  const activities = application?.activity ?? [];
  for (const activity of activities) {
    const attrs = activity.$ ?? (activity.$ = {});
    if (!String(attrs['android:name'] ?? '').endsWith('.MainActivity')) continue;
    const current = String(attrs['android:configChanges'] ?? '')
      .split('|')
      .map((s) => s.trim())
      .filter(Boolean);
    for (const flag of FOLD_CONFIG_CHANGES) {
      if (!current.includes(flag)) current.push(flag);
    }
    attrs['android:configChanges'] = current.join('|');
  }
  return manifest;
}

const PHONE_MAX_SW_DP = 600;
const POLICY_MARKER = 'applyOrientationPolicy';

const POLICY_MEMBERS = `
  private fun ${POLICY_MARKER}(config: android.content.res.Configuration) {
    requestedOrientation = if (config.smallestScreenWidthDp < ${PHONE_MAX_SW_DP}) {
      android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
    } else {
      android.content.pm.ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
    }
  }

  override fun onConfigurationChanged(newConfig: android.content.res.Configuration) {
    super.onConfigurationChanged(newConfig)
    ${POLICY_MARKER}(newConfig)
  }
`;

// app.json orientation is "default" so tablets and an open fold rotate; this keeps a phone-sized screen (the cover included) in portrait.
function addOrientationPolicy(source) {
  const src = String(source ?? '');
  if (src.includes(POLICY_MARKER)) return src;
  const classOpen = /class MainActivity\s*:\s*ReactActivity\(\)\s*\{/;
  const superCreate = /(\n([ \t]*)super\.onCreate\()/;
  if (!classOpen.test(src) || !superCreate.test(src)) return src;
  return src
    .replace(superCreate, `\n$2${POLICY_MARKER}(resources.configuration)$1`)
    .replace(classOpen, (open) => `${open}${POLICY_MEMBERS}`);
}

const PLUGIN = 'withFoldConfigChanges';

function patchMainActivity(activity, warn = (message) => WarningAggregator.addWarningAndroid(PLUGIN, message)) {
  if (activity?.language !== 'kt') {
    warn(`MainActivity is ${activity?.language ?? 'missing'}, not Kotlin: phones will rotate to landscape. Port ${POLICY_MARKER} by hand.`);
    return activity;
  }
  const contents = addOrientationPolicy(activity.contents);
  if (!contents.includes(POLICY_MARKER)) {
    warn(`MainActivity.kt no longer matches the Expo template this plugin patches: phones will rotate to landscape. Update ${PLUGIN}.`);
    return activity;
  }
  return { ...activity, contents };
}

function withFoldConfigChanges(config) {
  const withManifest = withAndroidManifest(config, (mod) => {
    mod.modResults = addFoldConfigChanges(mod.modResults);
    return mod;
  });
  return withMainActivity(withManifest, (mod) => {
    mod.modResults = patchMainActivity(mod.modResults);
    return mod;
  });
}

module.exports = withFoldConfigChanges;
module.exports.addFoldConfigChanges = addFoldConfigChanges;
module.exports.addOrientationPolicy = addOrientationPolicy;
module.exports.patchMainActivity = patchMainActivity;
module.exports.FOLD_CONFIG_CHANGES = FOLD_CONFIG_CHANGES;
module.exports.PHONE_MAX_SW_DP = PHONE_MAX_SW_DP;
