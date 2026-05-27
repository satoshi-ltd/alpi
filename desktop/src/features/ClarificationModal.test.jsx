import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, screen, cleanup, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

import ClarificationModal from "./ClarificationModal.jsx";

const SAMPLE_SINGLE = {
  request_id: "r1",
  question: "Pick one?",
  choices: [
    { label: "Python", description: "" },
    { label: "Rust", description: "" },
    { label: "Go", description: "" },
  ],
  allow_other: true,
  multi: false,
  deadline: Date.now() + 60_000,
};

const SAMPLE_MULTI = {
  request_id: "r-multi",
  question: "Pick many?",
  choices: [
    { label: "Sleep summary", description: "" },
    { label: "Training load", description: "" },
    { label: "Recovery breakdown", description: "" },
  ],
  allow_other: false,
  multi: true,
  deadline: Date.now() + 60_000,
};

describe("ClarificationModal", () => {
  beforeEach(() => {
    invoke.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("calls onResolved and clears state on a successful answer", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "clarification_respond") return { ok: true };
      return null;
    });
    const onResolved = vi.fn();
    render(<ClarificationModal requests={[SAMPLE_SINGLE]} onResolved={onResolved} />);

    fireEvent.click(screen.getByText("Rust"));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("clarification_respond", {
        requestId: "r1",
        choice: "Rust",
      });
    });
    expect(onResolved).toHaveBeenCalledWith("r1", "Rust");
  });

  it("keeps the modal open and surfaces the reason when the server rejects", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "clarification_respond") {
        return { ok: false, reason: "choice does not match any offered label" };
      }
      return null;
    });
    const onResolved = vi.fn();
    render(<ClarificationModal requests={[SAMPLE_SINGLE]} onResolved={onResolved} />);

    fireEvent.click(screen.getByText("Python"));

    await screen.findByText(/choice does not match any offered label/);
    expect(onResolved).not.toHaveBeenCalled();
    // Question is still on screen — the user can retry.
    expect(screen.getByText("Pick one?")).toBeInTheDocument();
  });

  it("multi mode wires JSON-array string of picked labels", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "clarification_respond") return { ok: true };
      return null;
    });
    render(<ClarificationModal requests={[SAMPLE_MULTI]} onResolved={() => {}} />);

    fireEvent.click(screen.getByText("Training load"));
    fireEvent.click(screen.getByText("Recovery breakdown"));
    fireEvent.click(screen.getByText(/Continue · 2/));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("clarification_respond", {
        requestId: "r-multi",
        choice: JSON.stringify(["Training load", "Recovery breakdown"]),
      });
    });
  });
});
