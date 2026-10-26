import { ACTIVITY_FILTERS, groupActivity } from '../../../../common/activityGroups.mjs';
import { mobile, space } from '../../theme/tokens';

export { ACTIVITY_FILTERS };

export const FILTER_LABEL = { all: 'All', needs: 'Needs you', failing: 'Failing', running: 'Running', upcoming: 'Upcoming' };
export const FILTER_EMPTY = {
  needs: 'Nothing needs you',
  failing: 'No failing jobs',
  running: 'Nothing running',
  upcoming: 'Nothing upcoming',
};

export const CHIP_H = space.s10 + space.s1;
export const CHIP_ROW_H = mobile.tap;
export const SECTION_H = space.s10 + space.s1;
export const GROUP_H = mobile.tap + space.s1;
export const JOB_ROW_H = mobile.tap + space.s5;
export const JOB_INDENT = space.s7 + space.s7;
export const RETRY_W = mobile.tap;

export function toGroups(activity, nowSec) {
  return groupActivity(
    { needs_you: activity?.needsYou, running: activity?.running, scheduled: activity?.scheduled },
    { nowMs: nowSec * 1000 },
  );
}

export function chipLabel(id, count) {
  return `${FILTER_LABEL[id]}, ${count}`;
}

export function groupLabel(name, count, agoText, expanded) {
  const jobs = count === 1 ? 'job' : 'jobs';
  return `${name}, ${count} failing ${jobs}${agoText ? `, latest ${agoText}` : ''}, ${expanded ? 'expanded' : 'collapsed'}`;
}

export function retryAllBody(count) {
  return `This starts one agent run per job, ${count} in all, and each run costs money.`;
}

export function textRoom(width, { left = 0, right = 0 } = {}) {
  return width - left - right;
}
