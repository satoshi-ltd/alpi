// Foreground-only toast for schedule events. Background-killed case is out of scope (would need APNs/FCM relay).

import { useToast } from '../components/Toast';
import { useEventEffect } from './useEvents';
import { buildScheduleToast } from '../lib/scheduleToast';

export function useScheduleToast() {
  const toast = useToast();
  useEventEffect(['schedule.done', 'schedule.failed'], (ev) => {
    const payload = buildScheduleToast(ev.event, ev.data);
    if (payload) toast(payload);
  });
}
