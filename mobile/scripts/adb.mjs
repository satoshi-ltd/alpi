export function queryAdb(run, adb, env, args) {
  const result = run(adb, args, { env, encoding: 'utf8', timeout: 15000 });
  if (result.error && result.error.code === 'ETIMEDOUT') return { answered: false, out: '' };
  if (result.error) throw result.error;
  return { answered: true, out: result.status === 0 ? result.stdout.trim() : '' };
}

export function parseDevices(stdout) {
  return stdout
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.split(/\s+/))
    .filter(([, state]) => state === 'device')
    .map(([serial]) => serial);
}

export function attachedSerials(run, adb, env) {
  const { answered, out } = queryAdb(run, adb, env, ['devices']);
  return answered ? parseDevices(out) : null;
}
