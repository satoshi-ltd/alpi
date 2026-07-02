import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const { notifyMock } = vi.hoisted(() => ({ notifyMock: vi.fn() }));

vi.mock("../../../primitives/Notification.jsx", () => ({
  useNotify: () => notifyMock,
}));

import { EmailCell, _clearEmailAccountsCache } from "./EmailCell.jsx";
import { _resetDaemonBus } from "../../../lib/daemon-bus.js";

const profile = { name: "concierge" };

const TWO_ACCOUNTS = [
  { id: "me_work_com", type: "imap", address: "me@work.com", configured: true },
  { id: "me_gmail_com", type: "gmail", address: "me@gmail.com", configured: true },
];

beforeEach(() => {
  _clearEmailAccountsCache();
  _resetDaemonBus();
  invoke.mockReset();
  notifyMock.mockReset();
  listen.mockReset();
  listen.mockImplementation(async () => () => {});
});

describe("EmailCell multi-account", () => {
  it("renders one chip per account labeled by address, no probe in the list", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return TWO_ACCOUNTS;
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    expect(await screen.findByRole("button", { name: "me@work.com" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "me@gmail.com" })).toBeInTheDocument();
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_status", {
        profile: "concierge",
        connectionId: "casa",
      });
    });
    expect(invoke).not.toHaveBeenCalledWith("probe_email", expect.anything());
  });

  it("shows 'none' when there are no accounts", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return [];
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    expect(await screen.findByText("none")).toBeInTheDocument();
  });

  it("renders cached accounts immediately while refreshing the selected daemon", async () => {
    invoke
      .mockResolvedValueOnce(TWO_ACCOUNTS)
      .mockResolvedValueOnce([
        ...TWO_ACCOUNTS,
        { id: "ops_example_com", type: "imap", address: "ops@example.com", configured: true },
      ]);
    const first = render(<EmailCell profile={profile} connectionId="casa" />);
    expect(await screen.findByRole("button", { name: "me@work.com" })).toBeInTheDocument();
    first.unmount();

    render(<EmailCell profile={profile} connectionId="casa" />);
    expect(screen.getByRole("button", { name: "me@work.com" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "ops@example.com" })).toBeInTheDocument();
    expect(invoke).toHaveBeenCalledTimes(2);
  });

  it("omits connectionId when no connection is selected", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return [];
      return null;
    });
    render(<EmailCell profile={profile} />);
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_status", { profile: "concierge" });
    });
  });

  it("refreshes the snapshot after adding an account when seeded by prefetched accounts", async () => {
    const onSnapshotRefresh = vi.fn(async () => {});
    invoke.mockImplementation(async (command) => {
      if (command === "email_add") return { ok: true, id: "me_x_com" };
      return null;
    });
    render(
      <EmailCell
        profile={profile}
        connectionId="casa"
        prefetched={[]}
        onSnapshotRefresh={onSnapshotRefresh}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "+ Add account" }));
    fireEvent.change(await screen.findByPlaceholderText("you@domain.com"), {
      target: { value: "me@x.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("app password if 2FA"), {
      target: { value: "secret" },
    });
    fireEvent.change(screen.getByPlaceholderText("imap.gmail.com"), {
      target: { value: "imap.x" },
    });
    fireEvent.change(screen.getByPlaceholderText("smtp.gmail.com"), {
      target: { value: "smtp.x" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add account" }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_add", expect.objectContaining({
        profile: "concierge",
        connectionId: "casa",
      }));
      expect(onSnapshotRefresh).toHaveBeenCalledTimes(1);
    });
    expect(invoke.mock.calls.some(([cmd]) => cmd === "email_status")).toBe(false);
  });

  it("reports loading around the status fetch", async () => {
    let resolveStatus;
    const onLoadingChange = vi.fn();
    invoke.mockImplementation((command) => {
      if (command === "email_status") {
        return new Promise((done) => { resolveStatus = done; });
      }
      return Promise.resolve(null);
    });
    render(
      <EmailCell
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

  it("creates an IMAP account via email_add (type toggle defaults to IMAP)", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return [];
      if (command === "email_add") return { ok: true, id: "me_x_com" };
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "+ Add account" }));
    expect(await screen.findByText("Add email account")).toBeInTheDocument();

    fireEvent.change(await screen.findByPlaceholderText("you@domain.com"), {
      target: { value: "me@x.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("app password if 2FA"), {
      target: { value: "secret" },
    });
    fireEvent.change(screen.getByPlaceholderText("imap.gmail.com"), {
      target: { value: "imap.x" },
    });
    fireEvent.change(screen.getByPlaceholderText("993"), { target: { value: "993" } });
    fireEvent.change(screen.getByPlaceholderText("smtp.gmail.com"), {
      target: { value: "smtp.x" },
    });
    fireEvent.change(screen.getByPlaceholderText("587"), { target: { value: "587" } });
    fireEvent.click(screen.getByRole("button", { name: "Add account" }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_add", {
        profile: "concierge",
        address: "me@x.com",
        password: "secret",
        imapHost: "imap.x",
        smtpHost: "smtp.x",
        imapPort: "993",
        smtpPort: "587",
        connectionId: "casa",
      });
    });
  });

  it("switches the create toggle to Gmail and authorizes with the entered address", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return [];
      if (command === "email_gmail_authorize") return null;
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "+ Add account" }));
    fireEvent.click(await screen.findByRole("button", { name: "Gmail" }));

    fireEvent.change(await screen.findByPlaceholderText("you@gmail.com"), {
      target: { value: "new@gmail.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Authorize" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_gmail_authorize", {
        profile: "concierge",
        address: "new@gmail.com",
        clientId: "",
        clientSecret: "",
        flowId: expect.any(String),
        connectionId: "casa",
      });
    });
  });

  it("opens the IMAP editor pre-filled from email_config and probes the single id", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return TWO_ACCOUNTS;
      if (command === "email_config") {
        return {
          type: "imap",
          address: "me@work.com",
          imap_host: "imap.work",
          imap_port: 993,
          smtp_host: "smtp.work",
          smtp_port: 587,
          password_set: true,
        };
      }
      if (command === "probe_email") return [{ name: "me_work_com", status: "on" }];
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "me@work.com" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_config", {
        profile: "concierge",
        id: "me_work_com",
        connectionId: "casa",
      });
    });
    expect(await screen.findByDisplayValue("imap.work")).toBeInTheDocument();
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("probe_email", {
        profile: "concierge",
        only: ["me_work_com"],
        connectionId: "casa",
      });
    });
  });

  it("removes an IMAP account by id via the confirm pattern", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return TWO_ACCOUNTS;
      if (command === "email_config") {
        return { type: "imap", address: "me@work.com", password_set: true };
      }
      if (command === "probe_email") return [{ name: "me_work_com", status: "on" }];
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "me@work.com" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove account" }));
    const removeButtons = await screen.findAllByRole("button", { name: "Remove" });
    fireEvent.click(removeButtons[removeButtons.length - 1]);
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_remove", {
        profile: "concierge",
        id: "me_work_com",
        connectionId: "casa",
      });
    });
  });

  it("tests an IMAP connection from the editor via probe_email", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return TWO_ACCOUNTS;
      if (command === "email_config") {
        return { type: "imap", address: "me@work.com", password_set: true };
      }
      if (command === "probe_email") return [{ name: "me_work_com", status: "on" }];
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "me@work.com" }));
    fireEvent.click(await screen.findByRole("button", { name: "Test connection" }));
    await waitFor(() => {
      expect(notifyMock).toHaveBeenCalledWith(
        expect.objectContaining({ message: "Connection OK", variant: "success" }),
      );
    });
  });

  it("saves an edited IMAP account with empty password (preserve unchanged)", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return TWO_ACCOUNTS;
      if (command === "email_config") {
        return {
          type: "imap", address: "me@work.com",
          imap_host: "imap.work", imap_port: 993,
          smtp_host: "smtp.work", smtp_port: 587,
          password_set: true,
        };
      }
      if (command === "probe_email") return [{ name: "me_work_com", status: "on" }];
      if (command === "email_add") return { ok: true, id: "me_work_com" };
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "me@work.com" }));
    expect(await screen.findByDisplayValue("imap.work")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_add", expect.objectContaining({
        profile: "concierge",
        address: "me@work.com",
        password: "",
        connectionId: "casa",
      }));
    });
  });

  it("saves a Gmail editor's client id/secret via provider_set_key, no re-auth", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return TWO_ACCOUNTS;
      if (command === "email_config") return { type: "gmail", address: "me@gmail.com" };
      if (command === "probe_email") return [{ name: "me_gmail_com", status: "on" }];
      if (command === "provider_set_key") return null;
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "me@gmail.com" }));
    fireEvent.change(await screen.findByPlaceholderText("OAuth desktop client id"), {
      target: { value: "cid-123" },
    });
    fireEvent.change(screen.getByPlaceholderText("OAuth client secret"), {
      target: { value: "sec-456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("provider_set_key", {
        profile: "concierge",
        key: "GMAIL_CLIENT_ID",
        value: "cid-123",
        connectionId: "casa",
      });
    });
    expect(invoke).toHaveBeenCalledWith("provider_set_key", {
      profile: "concierge",
      key: "GMAIL_CLIENT_SECRET",
      value: "sec-456",
      connectionId: "casa",
    });
    expect(invoke).not.toHaveBeenCalledWith("email_gmail_authorize", expect.anything());
  });

  it("removes a Gmail account by id from its editor", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "email_status") return TWO_ACCOUNTS;
      if (command === "email_config") return { type: "gmail", address: "me@gmail.com" };
      if (command === "probe_email") return [{ name: "me_gmail_com", status: "on" }];
      return null;
    });
    render(<EmailCell profile={profile} connectionId="casa" />);
    fireEvent.click(await screen.findByRole("button", { name: "me@gmail.com" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove account" }));
    const removeButtons = await screen.findAllByRole("button", { name: "Remove" });
    fireEvent.click(removeButtons[removeButtons.length - 1]);
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("email_remove", {
        profile: "concierge",
        id: "me_gmail_com",
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
      if (command === "email_status") return [];
      if (command === "email_gmail_authorize") return null;
      return null;
    });

    render(<EmailCell profile={profile} connectionId="mirai" />);
    fireEvent.click(await screen.findByRole("button", { name: "+ Add account" }));
    fireEvent.click(await screen.findByRole("button", { name: "Gmail" }));
    fireEvent.change(await screen.findByPlaceholderText("you@gmail.com"), {
      target: { value: "new@gmail.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Authorize" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith(
        "email_gmail_authorize",
        expect.objectContaining({ flowId: "mirai-flow", connectionId: "mirai" }),
      );
    });
    expect(gmailHandler).toBeTypeOf("function");

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

describe("EmailCell daemon events", () => {
  it("refetches accounts when the daemon emits email_changed for this (connection, profile)", async () => {
    let busCb;
    listen.mockImplementation(async (name, cb) => {
      if (name === "daemon-event") busCb = cb;
      return () => {};
    });
    invoke
      .mockResolvedValueOnce(TWO_ACCOUNTS)
      .mockResolvedValueOnce([
        ...TWO_ACCOUNTS,
        { id: "new_inbox", type: "imap", address: "new@inbox.com", configured: true },
      ]);

    render(<EmailCell profile={profile} connectionId="casa" />);
    expect(await screen.findByRole("button", { name: "me@work.com" })).toBeInTheDocument();

    await act(async () => {
      busCb({
        payload: {
          connection_id: "casa",
          frame: { event: "email_changed", data: { profile: "concierge" } },
        },
      });
    });
    expect(await screen.findByRole("button", { name: "new@inbox.com" })).toBeInTheDocument();
  });

  it("ignores email_changed for another profile", async () => {
    let busCb;
    listen.mockImplementation(async (name, cb) => {
      if (name === "daemon-event") busCb = cb;
      return () => {};
    });
    invoke.mockResolvedValueOnce(TWO_ACCOUNTS);

    render(<EmailCell profile={profile} connectionId="casa" />);
    expect(await screen.findByRole("button", { name: "me@work.com" })).toBeInTheDocument();
    invoke.mockClear();

    await act(async () => {
      busCb({
        payload: {
          connection_id: "casa",
          frame: { event: "email_changed", data: { profile: "someone-else" } },
        },
      });
      await new Promise((r) => setTimeout(r, 350));
    });
    expect(invoke).not.toHaveBeenCalled();
  });
});
