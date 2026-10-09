import { jobTitle } from '../../lib/scheduleFormat';

export const NEW_SCHEDULE_DRAFT = 'Schedule: ';

export function changeDraft(job) {
  return `Change the schedule “${jobTitle(job)}” (job ${job.id}): `;
}

export function chatWithDraft(profile, draft) {
  return `/chat/${profile}?draft=${encodeURIComponent(draft)}`;
}
