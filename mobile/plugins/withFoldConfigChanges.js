const { withAndroidManifest } = require('expo/config-plugins');

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

function withFoldConfigChanges(config) {
  return withAndroidManifest(config, (mod) => {
    mod.modResults = addFoldConfigChanges(mod.modResults);
    return mod;
  });
}

module.exports = withFoldConfigChanges;
module.exports.addFoldConfigChanges = addFoldConfigChanges;
module.exports.FOLD_CONFIG_CHANGES = FOLD_CONFIG_CHANGES;
