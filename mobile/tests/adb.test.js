import { describe, expect, it } from 'vitest';

import { attachedSerials, parseDevices, queryAdb } from '../scripts/adb.mjs';

const answer = (stdout, status = 0) => () => ({ status, stdout });
const timeout = () => ({ status: null, stdout: '', error: Object.assign(new Error('spawnSync adb ETIMEDOUT'), { code: 'ETIMEDOUT' }) });

describe('adb helpers', () => {
  it('keeps only devices that are ready', () => {
    expect(parseDevices('List of devices attached\nR5CX123\tdevice\nemulator-5554\toffline\nemulator-5556\tdevice\n')).toEqual(['R5CX123', 'emulator-5556']);
  });

  it('reports a timed-out adb as unanswered instead of an empty device list', () => {
    expect(queryAdb(timeout, 'adb', {}, ['devices'])).toEqual({ answered: false, out: '' });
    expect(attachedSerials(timeout, 'adb', {})).toBeNull();
  });

  it('an answered adb with no devices is an empty list, which is what may start an emulator', () => {
    expect(attachedSerials(answer('List of devices attached\n'), 'adb', {})).toEqual([]);
  });

  it('other spawn errors still fail loudly', () => {
    const broken = () => ({ error: Object.assign(new Error('ENOENT'), { code: 'ENOENT' }) });
    expect(() => queryAdb(broken, 'adb', {}, ['devices'])).toThrow('ENOENT');
  });
});
