import { deriveSummary, notificationTitle } from "./notificationSummary.mjs";

const FIRST_SENTENCE = /^(.{1,100}?[.!?])\s+(.+)$/u;

export const NO_PROSE = "Open it to read the detail.";

export function notificationParts(row) {
  const body = typeof row?.body === "string" ? row.body : "";
  const given = typeof row?.summary === "string" ? row.summary.trim() : "";
  const title = notificationTitle(row?.title);
  const summary = given || deriveSummary(body);
  let fromBody;
  const split = title ? null : summary.match(FIRST_SENTENCE);
  return {
    title,
    summary,
    body,
    get fromBody() {
      if (fromBody === undefined) fromBody = !given || given === deriveSummary(body);
      return fromBody;
    },
    get givenSummary() {
      return this.fromBody ? "" : given;
    },
    headline: title || (split ? split[1] : summary) || "—",
    preview: title ? summary : split ? split[2] : "",
  };
}
