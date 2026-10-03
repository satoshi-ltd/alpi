import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import SendButton, { foregroundOn } from "./SendButton.jsx";

describe("SendButton", () => {
  it.each([["send"], ["stop"]])("%s sits on the md control height beside the composer's icon buttons with the 4 px sheet corner", (variant) => {
    render(<SendButton variant={variant} canSend />);
    const btn = screen.getByRole("button");
    expect(btn.style.width).toBe("var(--ctrl-md)");
    expect(btn.style.height).toBe("var(--ctrl-md)");
    expect(btn.style.borderRadius).toBe("var(--r-xs)");
  });
});

describe("SendButton foreground", () => {
  const colourOf = (props) => {
    render(<SendButton canSend {...props} />);
    return screen.getByRole("button").style.color;
  };

  it.each([["#d4e157"], ["#f0b447"]])("reads ink on the light profile colour %s", (accent) => {
    expect(colourOf({ accent })).toBe("rgb(20, 17, 12)");
  });

  it("keeps white on a dark profile colour", () => {
    expect(colourOf({ accent: "#2b4c9a" })).toBe("rgb(255, 255, 255)");
  });

  it.each([[{}], [{ variant: "stop" }], [{ accent: "var(--accent)" }]])("paints the pane ground on a theme-ink fill %j", (props) => {
    expect(colourOf(props)).toBe("var(--bg-pane)");
  });

  it("dims the icon while there is nothing to send", () => {
    expect(colourOf({ canSend: false, accent: "#2b4c9a" })).toBe("var(--ink-3)");
  });

  it("picks the higher-contrast foreground", () => {
    expect(foregroundOn("#ffffff")).toBe("#14110c");
    expect(foregroundOn("#000000")).toBe("#ffffff");
  });
});
