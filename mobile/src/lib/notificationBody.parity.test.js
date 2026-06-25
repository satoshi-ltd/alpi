import { describe, it, expect } from "vitest";
import { parseNotificationBody as parseMobile, inlineSegments as inlineMobile } from "./notificationBody.js";
import { parseNotificationBody as parseDesktop, inlineSegments as inlineDesktop } from "../../../desktop/src/lib/notificationBody.js";
import { NOTIFICATION_CORPUS, INLINE_CORPUS } from "../../../desktop/src/lib/notificationBody.fixtures.js";

describe("notificationBody parser parity (mobile ↔ desktop)", () => {
  it.each(NOTIFICATION_CORPUS)("parseNotificationBody agrees on %j", (body) => {
    expect(parseDesktop(body)).toEqual(parseMobile(body));
  });

  it.each(INLINE_CORPUS)("inlineSegments agrees on %j", (text) => {
    expect(inlineDesktop(text)).toEqual(inlineMobile(text));
  });
});
