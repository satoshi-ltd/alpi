const DURATION_DEFAULT = 5000;

export function buildScheduleToast(event, data) {
  if (event !== 'schedule.done' && event !== 'schedule.failed') return null;

  const ok = event === 'schedule.done';
  const profile = (data?.profile || '').toString();
  const jobId = (data?.job_id || '').toString();
  const message = (data?.message || '').toString();
  const reply = (data?.reply || '').toString().trim();
  const silent = data?.silent === true;

  if (ok && silent) return null;

  if (reply) {
    return { title: profile, message: reply, duration: DURATION_DEFAULT };
  }
  if (ok) {
    return {
      title: `${profile} · schedule ran`,
      message: message ? `${jobId}: ${message}` : jobId,
      duration: DURATION_DEFAULT,
    };
  }
  return {
    title: `${profile} · schedule failed`,
    message: message ? `${jobId}: ${message}` : jobId,
    duration: DURATION_DEFAULT,
  };
}
