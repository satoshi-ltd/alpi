export function scheduleSummary(job) {
  if (!job) return "?";
  if (job.kind === "cron") return job.expression || "?";
  if (job.kind === "once") return `once ${job.run_at || "?"}`;
  if (job.kind === "inactivity") return `after ${job.after_hours ?? "?"}h`;
  return job.kind || "?";
}
