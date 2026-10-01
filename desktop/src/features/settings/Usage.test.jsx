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

describe("30-day footer total", () => {
  it("shows the 30-day total when the daemon provides it", () => {
    const days = makeDays([{ label: "M", tokIn: 1_000_000, tokOut: 0, today: true }]);
    render(
      <Usage
        days={days}
        accent="#3fb37a"
        total30={{ spanDays: 30, cost: 4.2, tokIn: 30_000_000, tokOut: 900_000 }}
      />,
    );
    expect(screen.getByText(/30-day total \$4\.20/)).toBeTruthy();
    expect(screen.getByText(/30M in \/ 900K out/)).toBeTruthy();
  });

  it("falls back to the 14-day total against older daemons", () => {
    const days = makeDays([{ label: "M", tokIn: 1_000_000, tokOut: 0, today: true }]);
    render(<Usage days={days} accent="#3fb37a" />);
    expect(screen.getByText(/14-day total/)).toBeTruthy();
  });
});

describe("Usage empty range", () => {
  it("collapses the track to one line when nothing was used", () => {
    const days = [
      { iso: "2026-07-13", label: "M", day: "7/13", tokIn: 0, tokOut: 0, cost: 0, today: false },
      { iso: "2026-07-14", label: "T", day: "7/14", tokIn: 0, tokOut: 0, cost: 0, today: true },
    ];
    const { container } = render(<Usage days={days} />);
    expect(screen.getByText("No usage in the last 2 days")).toBeInTheDocument();
    expect(container.querySelectorAll("[data-day]")).toHaveLength(0);
    expect(screen.queryByText(/day total/)).toBeNull();
    expect(screen.getByText("Avg / day")).toBeInTheDocument();
  });
});

describe("Usage bars follow the cost when the window pays", () => {
  const barPx = (container, iso) =>
    parseFloat(container.querySelector(`[data-day="${iso}"] > div:last-child`).style.height);

  const mixed = [
    { iso: "2026-06-01", day: "6/1", label: "M", tokIn: 9_000_000, tokOut: 100_000, cost: 0.05 },
    { iso: "2026-06-02", day: "6/2", label: "T", tokIn: 400_000, tokOut: 50_000, cost: 0.4 },
    { iso: "2026-06-03", day: "6/3", label: "W", tokIn: 0, tokOut: 0, cost: 0 },
    { iso: "2026-06-04", day: "6/4", label: "T", tokIn: 200_000, tokOut: 20_000, cost: 0.2, today: true },
  ];

  it("sizes bars by dollars: the heavy cached token day is not the tallest", () => {
    const { container } = render(<Usage days={mixed} accent="#3fb37a" />);

    const heavy = barPx(container, "2026-06-01");
    const dear = barPx(container, "2026-06-02");
    const today = barPx(container, "2026-06-04");
    expect(dear).toBeGreaterThan(today);
    expect(today).toBeGreaterThan(heavy);
    expect(dear / today).toBeCloseTo(2, 2);
    expect(barPx(container, "2026-06-03")).toBe(0);
    expect(screen.getByText(/bars by cost/)).toBeTruthy();
  });

  it("keeps a thin bar for a free day that did work inside a paid window", () => {
    const days = [
      { iso: "2026-06-01", day: "6/1", label: "M", tokIn: 5_000_000, tokOut: 0, cost: 0 },
      { iso: "2026-06-02", day: "6/2", label: "T", tokIn: 100_000, tokOut: 10_000, cost: 0.5, today: true },
    ];
    const { container } = render(<Usage days={days} accent="#3fb37a" />);

    expect(barPx(container, "2026-06-01")).toBe(3);
  });

  it("draws tokens when every day is free, as a local model does", () => {
    const days = [
      { iso: "2026-06-01", day: "6/1", label: "M", tokIn: 4_000_000, tokOut: 0, cost: 0 },
      { iso: "2026-06-02", day: "6/2", label: "T", tokIn: 1_000_000, tokOut: 0, cost: 0, today: true },
    ];
    const { container } = render(<Usage days={days} accent="#3fb37a" />);

    expect(barPx(container, "2026-06-01") / barPx(container, "2026-06-02")).toBeCloseTo(4, 0);
    expect(screen.getByText(/bars by tokens/)).toBeTruthy();
  });

  it("splits a paid bar by the price-weighted output share", () => {
    const days = [{ iso: "2026-06-01", day: "6/1", label: "M", tokIn: 1_000_000, tokOut: 250_000, cost: 0.3, today: true }];
    const { container } = render(<Usage days={days} accent="#3fb37a" />);

    const bar = container.querySelector('[data-day="2026-06-01"] > div:last-child');
    const out = parseFloat(bar.firstElementChild.style.height);
    const total = parseFloat(bar.style.height);
    expect(out / total).toBeCloseTo((250_000 * PRICE_OUT) / (1_000_000 * PRICE_IN + 250_000 * PRICE_OUT), 2);
  });

  it("makes the only paid day nearly full height beside free days", () => {
    const days = [
      { iso: "2026-06-01", day: "6/1", label: "M", tokIn: 1_000_000, tokOut: 0, cost: 0 },
      { iso: "2026-06-02", day: "6/2", label: "T", tokIn: 10_000, tokOut: 1_000, cost: 0.2, today: true },
    ];
    const { container } = render(<Usage days={days} accent="#3fb37a" />);

    expect(barPx(container, "2026-06-02")).toBeGreaterThan(90);
    expect(barPx(container, "2026-06-01")).toBe(3);
  });

  it("draws a day that cost money without tokens", () => {
    const days = [
      { iso: "2026-06-01", day: "6/1", label: "M", tokIn: 0, tokOut: 0, cost: 0.4, today: true },
      { iso: "2026-06-02", day: "6/2", label: "T", tokIn: 0, tokOut: 0, cost: 0.2 },
    ];
    const { container } = render(<Usage days={days} accent="#3fb37a" />);

    expect(barPx(container, "2026-06-01") / barPx(container, "2026-06-02")).toBeCloseTo(2, 2);
  });

  it("still shows cost with input and output tokens when hovering a bar", () => {
    const { container } = render(<Usage days={mixed} accent="#3fb37a" />);

    fireEvent.mouseEnter(container.querySelector('[data-day="2026-06-02"]'));

    expect(screen.getByText("$0.40")).toBeTruthy();
    expect(screen.getByText("400K")).toBeTruthy();
    expect(screen.getByText("50K")).toBeTruthy();
  });
});
