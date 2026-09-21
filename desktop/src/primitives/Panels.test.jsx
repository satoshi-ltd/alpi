import { describe, it, expect, vi } from "vitest";
import { act, render, fireEvent } from "@testing-library/react";
import { Scrim, ConnectionPanel } from "./Panels.jsx";

function esc() {
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
}

describe("Scrim", () => {
  it("closes on Escape (so every panel built on it gets ESC-to-close)", () => {
    const onClose = vi.fn();
    render(
      <Scrim onClose={onClose}>
        <div>body</div>
      </Scrim>,
    );
    esc();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("ignores non-Escape keys", () => {
    const onClose = vi.fn();
    render(
      <Scrim onClose={onClose}>
        <div>body</div>
      </Scrim>,
    );
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("removes the listener on unmount", () => {
    const onClose = vi.fn();
    const { unmount } = render(
      <Scrim onClose={onClose}>
        <div>body</div>
      </Scrim>,
    );
    unmount();
    esc();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("ignores Escape and backdrop clicks when not dismissable", () => {
    const onClose = vi.fn();
    const { getByText } = render(
      <Scrim onClose={onClose} dismissable={false}>
        <div>body</div>
      </Scrim>,
    );
    esc();
    fireEvent.click(getByText("body").parentElement);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("mounts outside the caller stacking context", () => {
    const { getByTestId, getByText } = render(
      <div data-testid="stacking-host">
        <Scrim onClose={() => {}}>
          <div>panel body</div>
        </Scrim>
      </div>,
    );

    const host = getByTestId("stacking-host");
    const scrim = getByText("panel body").parentElement;
    expect(host.contains(scrim)).toBe(false);
    expect(scrim.parentElement).toBe(document.body);
  });
});

describe("ConnectionPanel revoked row", () => {
  it("marks a revoked connection instead of showing it healthy", () => {
    const { getByText } = render(
      <ConnectionPanel
        open
        onClose={() => {}}
        activeId="local"
        connections={[
          {
            id: "r",
            kind: "remote",
            name: "alpi.mirai.com",
            host: "alpi.mirai.host:49250",
            status: "online",
            revoked: true,
            alpi_version: "0.14.10",
          },
        ]}
      />,
    );
    expect(getByText("revoked")).toBeTruthy();
  });
});

describe("ConnectionPanel rename", () => {
  const remote = {
    id: "r",
    kind: "remote",
    name: "casa",
    host: "casa:49200",
    status: "online",
    revoked: false,
    alpi_version: "0.15.0",
  };

  it("Forget asks first: cancelling keeps the row, confirming forgets it, and neither picks the row", () => {
    const onPick = vi.fn();
    const onForget = vi.fn();
    const utils = render(
      <ConnectionPanel open onClose={() => {}} activeId="local" connections={[remote]} onPick={onPick} onForget={onForget} onRename={() => {}} />,
    );
    expect(utils.getByLabelText("Rename")).toBeTruthy();
    fireEvent.click(utils.getByLabelText("Forget"));
    expect(utils.getByText("Forget casa?")).toBeTruthy();
    expect(onForget).not.toHaveBeenCalled();
    fireEvent.click(utils.getByRole("button", { name: "Cancel" }));
    expect(utils.queryByText("Forget casa?")).toBeNull();
    expect(onForget).not.toHaveBeenCalled();
    fireEvent.click(utils.getByLabelText("Forget"));
    fireEvent.click(utils.getByRole("button", { name: "Forget connection" }));
    expect(onForget).toHaveBeenCalledWith(remote);
    expect(utils.queryByText("Forget casa?")).toBeNull();
    expect(onPick).not.toHaveBeenCalled();
  });

  it("Escape closes the Forget confirm without closing the panel", () => {
    const onClose = vi.fn();
    const utils = render(
      <ConnectionPanel open onClose={onClose} activeId="local" connections={[remote]} onForget={() => {}} />,
    );
    fireEvent.click(utils.getByLabelText("Forget"));
    act(() => esc());
    expect(utils.queryByText("Forget casa?")).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("Rename turns the name into a field; Enter commits the trimmed value without picking the row", () => {
    const onRename = vi.fn();
    const onPick = vi.fn();
    const utils = render(
      <ConnectionPanel open onClose={() => {}} activeId="local" connections={[remote]} onPick={onPick} onRename={onRename} />,
    );
    fireEvent.click(utils.getByLabelText("Rename"));
    const input = utils.getByLabelText("Connection name");
    expect(input.value).toBe("casa");
    fireEvent.change(input, { target: { value: "  macbook-pro  " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onRename).toHaveBeenCalledWith(remote, "macbook-pro");
    expect(onPick).not.toHaveBeenCalled();
  });

  it("Escape discards the edit and the blur that follows does not commit it", () => {
    const onRename = vi.fn();
    const utils = render(
      <ConnectionPanel open onClose={() => {}} activeId="local" connections={[remote]} onRename={onRename} />,
    );
    fireEvent.click(utils.getByLabelText("Rename"));
    const input = utils.getByLabelText("Connection name");
    fireEvent.change(input, { target: { value: "otro" } });
    fireEvent.keyDown(input, { key: "Escape" });
    fireEvent.blur(input);
    expect(utils.queryByLabelText("Connection name")).toBeNull();
    expect(onRename).not.toHaveBeenCalled();
    expect(utils.getByText("casa")).toBeTruthy();
  });

  it("an unchanged or empty name is a no-op, and blur commits like Enter", () => {
    const onRename = vi.fn();
    const utils = render(
      <ConnectionPanel open onClose={() => {}} activeId="local" connections={[remote]} onRename={onRename} />,
    );
    fireEvent.click(utils.getByLabelText("Rename"));
    fireEvent.change(utils.getByLabelText("Connection name"), { target: { value: "   " } });
    fireEvent.keyDown(utils.getByLabelText("Connection name"), { key: "Enter" });
    expect(onRename).not.toHaveBeenCalled();
    fireEvent.click(utils.getByLabelText("Rename"));
    fireEvent.change(utils.getByLabelText("Connection name"), { target: { value: "mirai" } });
    fireEvent.blur(utils.getByLabelText("Connection name"));
    expect(onRename).toHaveBeenCalledWith(remote, "mirai");
  });

  it("the local daemon has no actions, and a panel without a rename handler hides Rename but keeps Forget", () => {
    const utils = render(
      <ConnectionPanel open onClose={() => {}} activeId="local" connections={[{ ...remote, id: "local", kind: "local", name: "Local daemon" }]} onRename={() => {}} onForget={() => {}} />,
    );
    expect(utils.queryByLabelText("Rename")).toBeNull();
    expect(utils.queryByLabelText("Forget")).toBeNull();
    utils.rerender(
      <ConnectionPanel open onClose={() => {}} activeId="local" connections={[remote]} onForget={() => {}} />,
    );
    expect(utils.queryByLabelText("Rename")).toBeNull();
    expect(utils.getByLabelText("Forget")).toBeTruthy();
  });
});

describe("ConnectionPanel locked", () => {
  it("hides the close button so the only path forward is adding a connection", () => {
    const onClose = vi.fn();
    const { queryByText, rerender } = render(
      <ConnectionPanel open locked={false} onClose={onClose} connections={[]} />,
    );
    expect(queryByText("Close")).toBeTruthy();
    rerender(
      <ConnectionPanel open locked onClose={onClose} connections={[]} />,
    );
    expect(queryByText("Close")).toBeNull();
    esc();
    expect(onClose).not.toHaveBeenCalled();
  });
});
