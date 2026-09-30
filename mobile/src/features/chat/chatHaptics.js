import * as haptics from '../../lib/haptics';

function play(name) {
  try {
    const fn = haptics[name];
    if (typeof fn === 'function') Promise.resolve(fn()).catch(() => {});
  } catch {
    return;
  }
}

export function sendHaptic() {
  play('tap');
}

export function longPressHaptic() {
  play('selection');
}
