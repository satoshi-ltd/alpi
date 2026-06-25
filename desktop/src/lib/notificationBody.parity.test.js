import { describe, it, expect } from "vitest";
import { parseNotificationBody as parseDesktop, inlineSegments as inlineDesktop } from "./notificationBody.js";
import { parseNotificationBody as parseMobile, inlineSegments as inlineMobile } from "../../../mobile/src/lib/notificationBody.js";
import { NOTIFICATION_CORPUS, INLINE_CORPUS } from "./notificationBody.fixtures.js";

describe("notificationBody parser parity (desktop ↔ mobile)", () => {
  it.each(NOTIFICATION_CORPUS)("parseNotificationBody agrees on %j", (body) => {
    expect(parseMobile(body)).toEqual(parseDesktop(body));
  });

  it.each(INLINE_CORPUS)("inlineSegments agrees on %j", (text) => {
    expect(inlineMobile(text)).toEqual(inlineDesktop(text));
  });
});
