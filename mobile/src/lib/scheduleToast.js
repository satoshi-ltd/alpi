const DURATION_DEFAULT = 5000;

export function buildScheduleToast(event, data) {
  if (event !== 'schedule.failed') return null;

  const profile = (data?.profile || '').toString();
  const name = (data?.title || '').toString() || (data?.job_id || '').toString();
  const reason = (data?.body || data?.message || '').toString().replace(/\n+/g, ' · ');

  return {
    title: `${profile} · schedule failed`,
    message: reason ? (name ? `${name}: ${reason}` : reason) : name,
    duration: DURATION_DEFAULT,
  };
}
