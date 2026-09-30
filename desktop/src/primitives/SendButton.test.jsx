import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import SendButton from "./SendButton.jsx";

describe("SendButton", () => {
  it.each([["send"], ["stop"]])("%s sits on the md control height beside the composer's icon buttons", (variant) => {
    render(<SendButton variant={variant} canSend />);
    const btn = screen.getByRole("button");
    expect(btn.style.width).toBe("var(--ctrl-md)");
    expect(btn.style.height).toBe("var(--ctrl-md)");
    expect(btn.style.borderRadius).toBe("calc(var(--ctrl-md) / 3)");
  });
});
