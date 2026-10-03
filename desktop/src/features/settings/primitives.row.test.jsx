import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QueryCtx } from "./SettingsNav.jsx";
import { Row } from "./primitives.jsx";

const draw = (query) =>
  render(
    <QueryCtx.Provider value={query}>
      <Row label="appearance" keywords="accent colour color fold origami">
        <span>control</span>
      </Row>
    </QueryCtx.Provider>,
  );

describe("Row keywords", () => {
  it.each(["appearance", "accent", "colour", "color", "fold", "origami", ""])("finds the row for %j", (query) => {
    draw(query);
    expect(screen.getByText("control").closest("[hidden]")).toBeNull();
  });

  it("hides the row when the query matches neither the label nor a keyword", () => {
    draw("budget");
    expect(screen.getByText("control").closest("[hidden]")).not.toBeNull();
  });
});
