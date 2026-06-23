import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const { notifyMock } = vi.hoisted(() => ({ notifyMock: vi.fn() }));

vi.mock("../../../primitives/Notification.jsx", () => ({
  useNotify: () => notifyMock,
}));

import { GatewaysCell } from "./GatewaysCell.jsx";

const profile = { name: "concierge" };

beforeEach(() => {
  invoke.mockReset();
  notifyMock.mockReset();
  listen.mockReset();
  listen.mockImplementation(async () => () => {});
});

describe("GatewaysCell multi-daemon scoping", () => {
  it("scopes status and probes to the selected connection", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "gateway_status") return [{ name: "telegram", configured: true }];
      if (command === "probe_gateways") return [{ name: "telegram", status: "on" }];
      return null;
    });
    render(<GatewaysCell profile={profile} connectionId="casa" />);
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("gateway_status", {
        profile: "concierge",
        connectionId: "casa",
      });
    });
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("probe_gateways", {
        profile: "concierge",
        only: ["telegram"],
        connectionId: "casa",
      });
    });
  });

  it("omits connectionId when no connection is selected", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "gateway_status") return [];
      return null;
    });
    render(<GatewaysCell profile={profile} />);
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("gateway_status", { profile: "concierge" });
    });
  });

  it("reports loading around the status+probe fetch", async () => {
    let resolveStatus;
    const onLoadingChange = vi.fn();
    invoke.mockImplementation((command) => {
      if (command === "gateway_status") {
        return new Promise((done) => { resolveStatus = done; });
      }
      return Promise.resolve(null);
    });
    render(
      <GatewaysCell
        profile={profile}
        connectionId="casa"
        onLoadingChange={onLoadingChange}
      />,
    );
    expect(onLoadingChange).toHaveBeenCalledWith(true);
    await act(async () => {
      resolveStatus([]);
      await Promise.resolve();
    });
    await waitFor(() => expect(onLoadingChange).toHaveBeenLastCalledWith(false));
  });

  it("ignores a late status response after switching daemons", async () => {
    let resolveCasa;
    const casa = new Promise((done) => { resolveCasa = done; });
    invoke.mockImplementation((command, args) => {
      if (command === "gateway_status") {
        if (args?.connectionId === "casa") return casa;
        if (args?.connectionId === "mirai") {
          return Promise.resolve([{ name: "telegram", configured: true }]);
        }
      }
      if (command === "probe_gateways") {
        return Promise.resolve([{ name: "telegram", status: "on" }]);
      }
      return Promise.resolve(null);
    });

    const { rerender } = render(<GatewaysCell profile={profile} connectionId="casa" />);
    rerender(<GatewaysCell profile={profile} connectionId="mirai" />);
    expect(await screen.findByRole("button", { name: "telegram" })).toBeInTheDocument();

    await act(async () => {
      resolveCasa([{ name: "matrix", configured: true }]);
      await Promise.resolve();
    });
    expect(screen.getByRole("button", { name: "telegram" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "matrix" })).toBeNull();
  });

  it("loads gateway config for the selected connection", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "gateway_status") return [{ name: "telegram", configured: false }];
      if (command === "gateway_config") return {};
      return null;
    });
    render(<GatewaysCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "telegram" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("gateway_config", {
        profile: "concierge",
        name: "telegram",
        connectionId: "casa",
      });
    });
  });

  it("scopes provider_set_key to the selected connection on save", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "gateway_status") return [{ name: "telegram", configured: false }];
      if (command === "gateway_config") return {};
      return null;
    });
    render(<GatewaysCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "telegram" }));
    const token = await screen.findByPlaceholderText("from @BotFather");
    fireEvent.change(token, { target: { value: "bot-123" } });
    const chats = screen.getByPlaceholderText(/comma-separated · empty = no inbound/);
    fireEvent.change(chats, { target: { value: "777" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("provider_set_key", {
        profile: "concierge",
        key: "TELEGRAM_BOT_TOKEN",
        value: "bot-123",
        connectionId: "casa",
      });
    });
    expect(invoke).toHaveBeenCalledWith("provider_set_key", {
      profile: "concierge",
      key: "TELEGRAM_ALLOWED_CHAT_IDS",
      value: "777",
      connectionId: "casa",
    });
  });

  it("scopes provider_unset_key to the selected connection", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "gateway_status") return [{ name: "imap", configured: true }];
      if (command === "probe_gateways") return [{ name: "imap", status: "on" }];
      if (command === "gateway_config") {
        return {
          IMAP_ADDRESS: "me@x.com",
          IMAP_PASSWORD: "***",
          IMAP_HOST: "imap.x",
          IMAP_PORT: "993",
          SMTP_HOST: "smtp.x",
          SMTP_PORT: "587",
        };
      }
      return null;
    });
    render(<GatewaysCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "imap" }));
    const port = await screen.findByDisplayValue("587");
    fireEvent.change(port, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("provider_unset_key", {
        profile: "concierge",
        key: "SMTP_PORT",
        connectionId: "casa",
      });
    });
  });

  it("scopes gateway_remove to the selected connection", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "gateway_status") return [{ name: "telegram", configured: true }];
      if (command === "probe_gateways") return [{ name: "telegram", status: "on" }];
      if (command === "gateway_config") {
        return { TELEGRAM_BOT_TOKEN: "tok", TELEGRAM_ALLOWED_CHAT_IDS: "1" };
      }
      return null;
    });
    render(<GatewaysCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "telegram" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
    const removeButtons = await screen.findAllByRole("button", { name: "Remove" });
    fireEvent.click(removeButtons[removeButtons.length - 1]);
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("gateway_remove", {
        profile: "concierge",
        name: "telegram",
        connectionId: "casa",
      });
    });
  });

  it("pins gmail authorize and paste to the selected connection", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "gateway_status") return [{ name: "gmail", configured: true }];
      if (command === "probe_gateways") return [{ name: "gmail", status: "on" }];
      if (command === "gateway_config") {
        return { GMAIL_CLIENT_ID: "stored-cid", GMAIL_ALLOWED_SENDERS: "boss@x.com" };
      }
      return null;
    });
    render(<GatewaysCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "gmail" }));

    await screen.findByDisplayValue("stored-cid");
    const secret = screen.getByPlaceholderText("OAuth client secret");
    fireEvent.change(secret, { target: { value: "csecret" } });
    fireEvent.click(screen.getByRole("button", { name: "Re-authorize" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("gateway_gmail_authorize", {
        profile: "concierge",
        clientId: "stored-cid",
        clientSecret: "csecret",
        allowedSenders: "boss@x.com",
        flowId: expect.any(String),
        connectionId: "casa",
      });
    });
    const authorizeCall = invoke.mock.calls.find(
      ([command]) => command === "gateway_gmail_authorize",
    );
    const flowId = authorizeCall[1].flowId;
    expect(flowId).toBeTruthy();

    const pasted = await screen.findByPlaceholderText(/127\.0\.0\.1/);
    fireEvent.change(pasted, { target: { value: "http://127.0.0.1:5/?code=abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Use pasted URL" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("gateway_gmail_paste", {
        pastedUrl: "http://127.0.0.1:5/?code=abc",
        flowId,
        connectionId: "casa",
      });
    });
  });

  it("ignores a gmail auth event from a previous flow", async () => {
    let gmailHandler;
    listen.mockImplementation(async (event, cb) => {
      if (event === "gmail-auth-event") gmailHandler = cb;
      return () => {};
    });
    const uuid = vi.spyOn(crypto, "randomUUID").mockReturnValue("mirai-flow");
    invoke.mockImplementation(async (command) => {
      if (command === "gateway_status") return [{ name: "gmail", configured: true }];
      if (command === "probe_gateways") return [{ name: "gmail", status: "on" }];
      if (command === "gateway_config") {
        return { GMAIL_CLIENT_ID: "stored", GMAIL_ALLOWED_SENDERS: "" };
      }
      if (command === "gateway_gmail_authorize") return null;
      return null;
    });

    render(<GatewaysCell profile={profile} connectionId="mirai" />);
    fireEvent.click(await screen.findByRole("button", { name: "gmail" }));
    await screen.findByDisplayValue("stored");
    fireEvent.change(screen.getByPlaceholderText("OAuth client secret"), {
      target: { value: "sec" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Re-authorize" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith(
        "gateway_gmail_authorize",
        expect.objectContaining({ flowId: "mirai-flow", connectionId: "mirai" }),
      );
    });
    expect(gmailHandler).toBeTypeOf("function");

    await act(async () => {
      gmailHandler({
        payload: {
          event: "authorized",
          email: "wrong@casa",
          flow_id: "casa-flow",
          connection_id: "casa",
        },
      });
      await Promise.resolve();
    });
    expect(notifyMock).not.toHaveBeenCalled();

    await act(async () => {
      gmailHandler({
        payload: {
          event: "authorized",
          email: "wrong@casa",
          flow_id: "mirai-flow",
          connection_id: "casa",
        },
      });
      await Promise.resolve();
    });
    expect(notifyMock).not.toHaveBeenCalled();

    await act(async () => {
      gmailHandler({
        payload: {
          event: "authorized",
          email: "right@mirai",
          flow_id: "mirai-flow",
          connection_id: "mirai",
        },
      });
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(notifyMock).toHaveBeenCalledWith(
        expect.objectContaining({
          message: expect.stringContaining("right@mirai"),
          variant: "success",
        }),
      );
    });
    uuid.mockRestore();
  });
});
