const DURATION_DEFAULT = 5000;

export function buildScheduleToast(event, data) {
  if (event !== 'schedule.failed') return null;

  const profile = (data?.profile || '').toString();
  const jobId = (data?.job_id || '').toString();
  const message = (data?.message || '').toString();

  return {
    title: `${profile} · schedule failed`,
    message: message ? `${jobId}: ${message}` : jobId,
    duration: DURATION_DEFAULT,
  };
}
