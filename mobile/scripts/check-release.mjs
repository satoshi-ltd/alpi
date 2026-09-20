import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
const fail = (message) => {
  console.error(message);
  process.exit(1);
};

const { version } = read('package.json');
if (!/^\d+\.\d+\.\d+$/.test(version)) fail(`Expected an x.y.z release version, got ${version}`);

const { expo } = read('app.json');
if (expo.version !== version) fail(`package.json is ${version} but app.json is ${expo.version}`);

const build = String(expo.android.versionCode);
if (build !== String(expo.ios.buildNumber)) {
  fail(`android.versionCode ${build} and ios.buildNumber ${expo.ios.buildNumber} disagree`);
}

// EAS runs `npm ci`, so a lock that disagrees with the manifest fails the build there and
// would fail here too — catch it before a local compile spends the time.
const lock = read('package-lock.json');
if (lock.version !== version || lock.packages?.['']?.version !== version) {
  fail(`package-lock.json is ${lock.version}/${lock.packages?.['']?.version}, not ${version}`);
}

const changelog = path.join(root, 'CHANGELOG.md');
if (!fs.existsSync(changelog)) fail('CHANGELOG.md is missing');
if (!fs.readFileSync(changelog, 'utf8').includes(`## v${version} —`)) {
  fail(`CHANGELOG.md has no entry for v${version}`);
}

console.log(`Release manifests agree: v${version}, build ${build}`);
