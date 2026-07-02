import { describe, it, expect } from "vitest";
import { visibleWindow } from "./chatWindow.js";

const turns = (n) => Array.from({ length: n }, (_, i) => ({ user: `u${i}` }));

describe("visibleWindow", () => {
  it("returns the newest page in inverted order", () => {
    const out = visibleWindow(turns(5), 2);
    expect(out.map((x) => x.turn.user)).toEqual(["u4", "u3"]);
  });

  it("caps at the available turns when the page is bigger than the list", () => {
    const out = visibleWindow(turns(2), 30);
    expect(out).toHaveLength(2);
  });

  it("offsets turnIndex by turnsBase so a tail slice yields ABSOLUTE indices for rewrite_from_turn", () => {
    const out = visibleWindow(turns(3), 3, 40);
    expect(out.map((x) => x.turnIndex)).toEqual([42, 41, 40]);
  });

  it("defaults to zero base for full transcripts", () => {
    const out = visibleWindow(turns(2), 2);
    expect(out.map((x) => x.turnIndex)).toEqual([1, 0]);
  });
});
