export function scheduleSummary(job) {
  if (!job) return "?";
  if (job.kind === "cron") return job.expression || "?";
  if (job.kind === "once") return `once ${job.run_at || "?"}`;
  if (job.kind === "inactivity") return `after ${job.after_hours ?? "?"}h`;
  return job.kind || "?";
}

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const SHORT_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const pad = (n) => String(n).padStart(2, "0");
const isInt = (v) => /^\d+$/.test(v);

function dayList(field) {
  const days = new Set();
  for (const part of field.split(",")) {
    const range = /^(\d)-(\d)$/.exec(part);
    if (range) {
      const [from, to] = [Number(range[1]), Number(range[2])];
      if (from > to) return null;
      for (let d = from; d <= to; d++) days.add(d % 7);
    } else if (/^\d$/.test(part)) {
      days.add(Number(part) % 7);
    } else {
      return null;
    }
  }
  return days.size ? [...days].sort((a, b) => ((a + 6) % 7) - ((b + 6) % 7)) : null;
}

function describeDays(days) {
  const key = [...days].sort().join(",");
  if (key === "1,2,3,4,5") return "every weekday";
  if (key === "0,6") return "every weekend day";
  if (days.length === 7) return "every day";
  if (days.length === 1) return `every ${DAYS[days[0]]}`;
  return `every ${days.map((d) => SHORT_DAYS[d]).join(", ")}`;
}

export function describeCron(expression) {
  const fields = String(expression || "").trim().split(/\s+/);
  if (fields.length !== 5) return null;
  const [min, hour, dom, mon, dow] = fields;
  if (mon !== "*") return null;
  const step = (v) => (/^\*\/(\d+)$/.exec(v) ? Number(v.slice(2)) : null);
  if (dom === "*" && dow === "*") {
    const minStep = step(min);
    if (minStep && hour === "*") {
      if (60 % minStep !== 0) return null;
      return minStep === 1 ? "every minute" : `every ${minStep} minutes`;
    }
    if (isInt(min) && hour === "*") return Number(min) === 0 ? "every hour" : `every hour at :${pad(min)}`;
    const hourStep = step(hour);
    if (isInt(min) && hourStep) {
      if (24 % hourStep !== 0) return null;
      const every = hourStep === 1 ? "every hour" : `every ${hourStep} hours`;
      return Number(min) === 0 ? every : `${every} at :${pad(min)}`;
    }
  }
  if (!isInt(min) || !isInt(hour)) return null;
  const at = `at ${pad(hour)}:${pad(min)}`;
  if (dom === "*" && dow === "*") return `every day ${at}`;
  if (dom === "*") {
    const days = dayList(dow);
    return days ? `${describeDays(days)} ${at}` : null;
  }
  if (isInt(dom) && dow === "*") return `on day ${Number(dom)} of every month ${at}`;
  return null;
}

function offsetOf(iso) {
  const m = /(Z|([+-])(\d{2}):?(\d{2}))$/.exec(String(iso || ""));
  if (!m) return null;
  if (m[1] === "Z") return 0;
  return (m[2] === "-" ? -1 : 1) * (Number(m[3]) * 60 + Number(m[4]));
}

function viewerOffset(iso, given) {
  if (given != null) return given;
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? null : -new Date(ms).getTimezoneOffset();
}

function zoneLabel(minutes) {
  if (minutes === 0) return "UTC";
  const abs = Math.abs(minutes);
  return `UTC${minutes < 0 ? "-" : "+"}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

function onceLine(y, mo, d, h, mi) {
  const weekday = SHORT_DAYS[new Date(Date.UTC(y, mo - 1, d)).getUTCDay()];
  return `once, ${weekday} ${d} ${MONTHS[mo - 1]} at ${pad(h)}:${pad(mi)}`;
}

export function describeOnce(runAt, viewer = null) {
  const text = String(runAt || "");
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(text);
  if (!m) return runAt ? `once, ${runAt}` : "once";
  const ms = Date.parse(text);
  if (offsetOf(text) != null && !Number.isNaN(ms)) {
    const local = new Date(ms + viewerOffset(text, viewer) * 60000);
    return onceLine(local.getUTCFullYear(), local.getUTCMonth() + 1, local.getUTCDate(), local.getUTCHours(), local.getUTCMinutes());
  }
  return onceLine(Number(m[1]), Number(m[2]), Number(m[3]), Number(m[4]), Number(m[5]));
}

export function describeInactivity(afterHours) {
  const hours = Number(afterHours);
  if (!Number.isFinite(hours) || hours <= 0) return "after a quiet spell";
  if (hours % 24 === 0) return `after ${hours / 24} day${hours === 24 ? "" : "s"} without a message`;
  return `after ${hours} hour${hours === 1 ? "" : "s"} without a message`;
}

function daemonZone(job, viewer) {
  const daemon = offsetOf(job.next_fire);
  if (daemon == null) return "";
  return viewerOffset(job.next_fire, viewer) === daemon ? "" : ` (${zoneLabel(daemon)})`;
}

export function describeWhen(job, viewer = null) {
  if (!job) return "?";
  if (job.kind === "once") {
    const text = describeOnce(job.run_at, viewer);
    return offsetOf(job.run_at) == null ? text + daemonZone(job, viewer) : text;
  }
  if (job.kind === "inactivity") return describeInactivity(job.after_hours);
  if (job.kind === "cron") {
    const text = describeCron(job.expression);
    return text ? text + daemonZone(job, viewer) : `cron ${job.expression || "?"}`;
  }
  return job.kind || "?";
}

export function describeTimeout(job) {
  const secs = Number(job?.run_timeout);
  if (!Number.isFinite(secs) || secs <= 0) return null;
  return secs % 60 === 0 ? `${secs / 60} min timeout` : `${secs} s timeout`;
}

export function rawWhen(job) {
  if (job?.kind === "cron") return job.expression || null;
  if (job?.kind === "once") return job.run_at || null;
  if (job?.kind === "inactivity") return job.after_hours != null ? `after ${job.after_hours}h` : null;
  return null;
}
