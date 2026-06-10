import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import Usage, { fmtTok } from "./Usage.jsx";

const PRICE_IN = 0.15 / 1e6;
const PRICE_OUT = 0.6 / 1e6;

function makeDays(specs) {
  return specs.map((s, i) => {
    const tokIn = s.tokIn ?? 0;
    const tokOut = s.tokOut ?? 0;
    return {
      label: s.label ?? "M",
      day: s.day ?? `6/${i + 1}`,
      iso: s.iso ?? `2026-06-${String(i + 1).padStart(2, "0")}`,
      tokIn,
      tokOut,
      cost: tokIn * PRICE_IN + tokOut * PRICE_OUT,
      today: !!s.today,
    };
  });
}

describe("fmtTok", () => {
  it("formats millions and thousands with one decimal until 3 integer digits", () => {
    expect(fmtTok(1_234_567)).toBe("1.2M");
    expect(fmtTok(13_000_000)).toBe("13M");
    expect(fmtTok(184_000)).toBe("184K");
    expect(fmtTok(408_000)).toBe("408K");
    expect(fmtTok(1_500)).toBe("1.5K");
    expect(fmtTok(999)).toBe("999");
    expect(fmtTok(0)).toBe("0");
  });
});

describe("Usage", () => {
  it("renders nothing without days", () => {
    const { container } = render(<Usage days={[]} accent="#3fb37a" />);
    expect(container.firstChild).toBeNull();
  });

  it("shows today's cost, input and output", () => {
    const days = makeDays([
      { tokIn: 0, tokOut: 0 },
      { tokIn: 1_500_000, tokOut: 408_000, today: true },
    ]);
    render(<Usage days={days} accent="#3fb37a" />);
    expect(screen.getByText("$0.47")).toBeTruthy();
    expect(screen.getByText("1.5M")).toBeTruthy();
    expect(screen.getByText("408K")).toBeTruthy();
  });

  it("profile mode shows Cap / day with percent left", () => {
    const days = makeDays([{ tokIn: 1_000_000, tokOut: 0, today: true }]);
    render(<Usage days={days} accent="#3fb37a" capLine={1.0} />);
    expect(screen.getByText("Cap / day")).toBeTruthy();
    expect(screen.getByText("$1.00")).toBeTruthy();
    expect(screen.getByText("85% left")).toBeTruthy();
  });

  it("workgroup mode shows Avg / day instead of a cap", () => {
    const days = makeDays([
      { tokIn: 1_000_000, tokOut: 0 },
      { tokIn: 1_000_000, tokOut: 0, today: true },
    ]);
    render(<Usage days={days} accent="#3fb37a" />);
    expect(screen.getByText("Avg / day")).toBeTruthy();
    expect(screen.queryByText("Cap / day")).toBeNull();
  });

  it("renders a label per day and a 14-day footer total", () => {
    const days = makeDays(
      Array.from({ length: 14 }, (_, i) => ({
        label: "WTFSSMT"[i % 7],
        tokIn: 1_000_000,
        tokOut: 0,
        today: i === 13,
      })),
    );
    const { container } = render(<Usage days={days} accent="#3fb37a" />);
    expect(container.querySelectorAll("[data-day]").length).toBe(14);
    expect(screen.getByText(/14-day total \$2\.10/)).toBeTruthy();
    expect(screen.getByText(/14M in \/ 0 out/)).toBeTruthy();
  });

  it("never draws a cap line — the cap lives only in the Cap / day stat", () => {
    const days = makeDays([{ tokIn: 1_000_000, tokOut: 0, today: true }]);
    const { container } = render(<Usage days={days} accent="#3fb37a" capLine={0.2} />);
    expect(container.textContent).not.toContain("/day");
    expect(container.textContent).toContain("Cap / day");
  });

  it("sizes bars by token volume when the whole window is free (cost 0)", () => {
    const days = [
      { iso: "2026-06-01", label: "M", day: "6/1", tokIn: 0, tokOut: 0, cost: 0, today: false },
      { iso: "2026-06-02", label: "T", day: "6/2", tokIn: 200_000, tokOut: 1_000, cost: 0, today: true },
    ];
    const { container } = render(<Usage days={days} accent="#3fb37a" />);
    expect(screen.getByText("200K")).toBeTruthy();
    expect(screen.getByText("1K")).toBeTruthy();
    const bar = container.querySelector('[data-day="2026-06-02"] div[style]');
    expect(parseFloat(bar.style.height)).toBeGreaterThan(0);
  });

  it("reveals a per-day tooltip on hover", () => {
    const days = makeDays([
      { day: "6/2", tokIn: 1_100_000, tokOut: 312_000 },
      { tokIn: 0, tokOut: 0, today: true },
    ]);
    const { container } = render(<Usage days={days} accent="#3fb37a" />);
    fireEvent.mouseEnter(container.querySelector('[data-day="2026-06-01"]'));
    expect(screen.getByText("6/2")).toBeTruthy();
    expect(screen.getByText("$0.35")).toBeTruthy();
    expect(screen.getByText("1.1M")).toBeTruthy();
    expect(screen.getByText("312K")).toBeTruthy();
  });

  it("an empty day (no tokens, no cost) shows no tooltip on hover", () => {
    const days = makeDays([
      { day: "6/1", tokIn: 0, tokOut: 0 },
      { day: "6/2", tokIn: 1_000_000, tokOut: 0, today: true },
    ]);
    const { container } = render(<Usage days={days} accent="#3fb37a" />);
    fireEvent.mouseEnter(container.querySelector('[data-day="2026-06-01"]'));
    // The tooltip day header is the only place d.day renders.
    expect(screen.queryByText("6/1")).toBeNull();
  });

  it("a free-model day (tokens but $0) still gets its tooltip", () => {
    const days = [
      { iso: "2026-06-01", label: "M", day: "6/1", tokIn: 50_000, tokOut: 2_000, cost: 0, today: false },
      { iso: "2026-06-02", label: "T", day: "6/2", tokIn: 0, tokOut: 0, cost: 0, today: true },
    ];
    const { container } = render(<Usage days={days} accent="#3fb37a" />);
    fireEvent.mouseEnter(container.querySelector('[data-day="2026-06-01"]'));
    expect(screen.getByText("6/1")).toBeTruthy();
    expect(screen.getByText("50K")).toBeTruthy();
  });
});
