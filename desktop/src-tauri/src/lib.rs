mod event_dispatch;
mod host_client;
mod home;
mod notifications;
mod state;
mod tray;
pub mod tts;
mod watcher;

use std::collections::HashMap;
use std::process::{Command, Stdio};
use std::sync::{Mutex, OnceLock};
use std::thread;

use tauri::menu::{AboutMetadataBuilder, Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::Manager;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};
use tauri_plugin_dialog::DialogExt;

fn active_chats() -> &'static Mutex<HashMap<String, String>> {
    static SLOT: OnceLock<Mutex<HashMap<String, String>>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(HashMap::new()))
}

fn active_chat_key(connection_id: &str, profile: &str) -> String {
    format!("{connection_id}\0{profile}")
}

use serde::Serialize;
use tauri::{AppHandle, Emitter};

use crate::state::{DecryptedMessage, SessionEntry};

#[derive(Serialize, Clone)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum ChatEvent {
    // First frame of every host.chat.send stream — the session id is pinned BEFORE the engine starts so replay (host.chat.events_since) works even on brand-new sessions whose id the client hasn't seen yet.
    SessionStart {
        request_id: String,
        session_id: String,
    },
    ToolStart {
        request_id: String,
        tool_id: String,
        name: String,
        preview: String,
        args: serde_json::Value,
    },
    ToolState {
        request_id: String,
        tool_id: String,
        name: String,
        text: String,
        ok: bool,
    },
    ToolEnd {
        request_id: String,
        tool_id: String,
        name: String,
        ok: bool,
        output: String,
    },
    ReasoningDelta {
        request_id: String,
        text: String,
    },
    AssistantDelta {
        request_id: String,
        text: String,
    },
    Error {
        request_id: String,
        text: String,
    },
    Interrupted {
        request_id: String,
    },
    AutoCompact {
        request_id: String,
        text: String,
        tokens_before: u64,
        tokens_after: u64,
    },
    Usage {
        request_id: String,
        tokens_in: u64,
        tokens_out: u64,
        cached_in: u64,
        context_tokens: u64,
        cost: f64,
        model: String,
    },
    Reply {
        request_id: String,
        text: String,
        session_id: String,
    },
    Done {
        request_id: String,
        session_id: String,
    },
    Heartbeat {
        request_id: String,
    },
}

#[tauri::command]
async fn profiles() -> serde_json::Value {
    off_main(|| host_array_value("host.profiles.list", serde_json::json!({}), "profiles"))
        .await
        .unwrap_or(serde_json::Value::Array(vec![]))
}

#[tauri::command]
async fn profile_tools(profile: String, connection_id: Option<String>) -> serde_json::Value {
    off_main(move || host_array_value_for(
        connection_id.as_deref(),
        "host.tools.list",
        serde_json::json!({ "profile": profile }),
        "tools",
    ))
    .await
    .unwrap_or(serde_json::Value::Array(vec![]))
}

#[tauri::command]
async fn profile_skills(profile: String, connection_id: Option<String>) -> serde_json::Value {
    off_main(move || host_array_value_for(
        connection_id.as_deref(),
        "host.skills.list",
        serde_json::json!({ "profile": profile }),
        "skills",
    ))
    .await
    .unwrap_or(serde_json::Value::Array(vec![]))
}

#[tauri::command]
async fn profile_skill_read(
    profile: String,
    name: String,
    category: Option<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let mut params = serde_json::json!({ "profile": profile, "name": name });
        if let Some(cat) = category {
            params["category"] = serde_json::Value::String(cat);
        }
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.skill.read", params),
            None => host_client::call("host.skill.read", params),
        }
        .map(|v| v.get("skill").cloned().unwrap_or(serde_json::Value::Null))
        .map_err(|e| e.to_string())
    })
    .await?
}

#[tauri::command]
async fn profile_skill_file(
    profile: String,
    name: String,
    path: String,
    category: Option<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let mut params = serde_json::json!({ "profile": profile, "name": name, "path": path });
        if let Some(cat) = category {
            params["category"] = serde_json::Value::String(cat);
        }
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.skill.file", params),
            None => host_client::call("host.skill.file", params),
        }
        .map(|v| v.get("file").cloned().unwrap_or(serde_json::Value::Null))
        .map_err(|e| e.to_string())
    })
    .await?
}

#[tauri::command]
async fn profile_detail(
    profile: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let params = serde_json::json!({ "profile": profile });
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.profile.detail", params),
            None => host_client::call("host.profile.detail", params),
        }
        .map_err(|e| e.to_string())
    })
    .await?
}

#[tauri::command]
async fn settings_profile_snapshot(
    profile: String,
    connection_id: Option<String>,
    sections: Option<Vec<String>>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let mut params = serde_json::json!({ "profile": profile });
        if let Some(sections) = sections {
            params["sections"] = serde_json::json!(sections);
        }
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.settings.profile_snapshot", params),
            None => host_client::call("host.settings.profile_snapshot", params),
        }
        .map_err(|e| e.to_string())
    })
    .await?
}

#[tauri::command]
async fn usage_daily(
    profile: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let params = serde_json::json!({ "profile": profile });
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.usage.daily", params),
            None => host_client::call("host.usage.daily", params),
        }
        .map_err(|e| e.to_string())
    })
    .await?
}

#[tauri::command]
async fn workgroup_usage_daily(
    profile: String,
    wg_id: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let params = serde_json::json!({ "profile": profile, "wg_id": wg_id });
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.usage.workgroup.daily", params),
            None => host_client::call("host.usage.workgroup.daily", params),
        }
        .map_err(|e| e.to_string())
    })
    .await?
}

#[tauri::command]
async fn profile_memory(
    profile: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let mut out = serde_json::Map::new();
        for name in ["USER.md", "MEMORY.md", "AGENT.md"] {
            let rel = format!("memories/{name}");
            let params = serde_json::json!({ "profile": profile, "rel_path": rel });
            let text = match connection_id.as_deref() {
                Some(cid) => host_client::call_for(cid, "host.profile.read_file", params),
                None => host_client::call("host.profile.read_file", params),
            }
            .ok()
            .and_then(|v| v.get("text").and_then(|t| t.as_str()).map(String::from))
            .unwrap_or_default();
            out.insert(name.to_string(), serde_json::Value::String(text));
        }
        Ok(serde_json::Value::Object(out))
    })
    .await?
}

#[tauri::command]
async fn memory_usage(
    profile: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let params = serde_json::json!({ "profile": profile });
        let res = match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.profile.memory_usage", params),
            None => host_client::call("host.profile.memory_usage", params),
        }?;
        Ok(res.get("files").cloned().unwrap_or(serde_json::Value::Null))
    })
    .await?
}

#[tauri::command]
async fn memory_read(
    profile: String,
    name: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let params = serde_json::json!({ "profile": profile, "name": name });
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.profile.memory_read", params),
            None => host_client::call("host.profile.memory_read", params),
        }
    })
    .await?
}

#[tauri::command]
async fn memory_write(
    profile: String,
    name: String,
    text: String,
    rev: Option<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let mut params = serde_json::json!({ "profile": profile, "name": name, "text": text });
        if let Some(r) = rev {
            params["rev"] = serde_json::Value::String(r);
        }
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.profile.memory_write", params),
            None => host_client::call("host.profile.memory_write", params),
        }
    })
    .await?
}

#[tauri::command]
async fn profile_summaries(connection_id: Option<String>) -> Result<serde_json::Value, String> {
    off_main(move || {
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.profile.summaries", serde_json::json!({})),
            None => host_client::call("host.profile.summaries", serde_json::json!({})),
        }
        .map(|v| {
            v.get("profiles")
                .cloned()
                .unwrap_or_else(|| serde_json::Value::Array(vec![]))
        })
        .map_err(|e| e.to_string())
    })
    .await?
}

#[tauri::command]
async fn host_connections() -> serde_json::Value {
    off_main(host_client::connections_for_ui)
        .await
        .unwrap_or(serde_json::Value::Null)
}

#[tauri::command]
async fn host_connection_set_active(id: String) -> Result<(), String> {
    off_main(move || host_client::set_active_connection(id)).await?
}

#[tauri::command]
async fn host_connection_forget(id: String) -> Result<(), String> {
    off_main(move || host_client::forget_connection(id)).await?
}

#[tauri::command]
async fn host_connection_add_remote(
    name: String,
    url: String,
    token: Option<String>,
    pairing_token: Option<String>,
) -> Result<String, String> {
    off_main(move || {
        let device_name = std::env::var("HOSTNAME").unwrap_or_else(|_| "Desktop".into());
        let id = if let Some(grant) = pairing_token.filter(|value| !value.trim().is_empty()) {
            host_client::exchange_and_add_remote_connection(
                name,
                url,
                grant,
                device_name,
                env!("CARGO_PKG_VERSION").to_string(),
            )?
        } else {
            let token = token.filter(|value| !value.trim().is_empty())
                .ok_or_else(|| "pairing payload needs a token".to_string())?;
            let id = host_client::add_remote_connection(name, url, token)?;
            let _ = host_client::call_for(
                &id,
                "host.connections.register_device",
                serde_json::json!({
                    "client": "desktop",
                    "name": device_name,
                    "app_version": env!("CARGO_PKG_VERSION"),
                }),
            );
            id
        };
        Ok(id)
    }).await?
}

fn spawn_background(name: &str, f: impl FnOnce() + Send + 'static) {
    if let Err(e) = thread::Builder::new().name(name.to_string()).spawn(f) {
        eprintln!("background task {name} not started: {e}");
    }
}

// Sync #[tauri::command]s run on the main thread — daemon I/O there freezes the whole window for the full read timeout, so every blocking call goes through here.
async fn off_main<T, F>(f: F) -> Result<T, String>
where
    T: Send + 'static,
    F: FnOnce() -> T + Send + 'static,
{
    tauri::async_runtime::spawn_blocking(f)
        .await
        .map_err(|e| format!("join: {e}"))
}

#[tauri::command]
fn host_connections_probe_active() {
    spawn_background("probe-active", host_client::probe_active);
}

#[tauri::command]
fn host_connections_probe_all() {
    spawn_background("probe-all", host_client::probe_all);
}

// Synchronous probe of one connection — used by onSetHostConnection to avoid racing the loop.
#[tauri::command]
async fn host_connection_probe(id: String) -> String {
    tauri::async_runtime::spawn_blocking(move || {
        let state = host_client::load_connections();
        if let Some(conn) = state.connections.iter().find(|c| c.id() == id) {
            host_client::probe_connection(conn);
        }
        match host_client::status_for(&id).0 {
            host_client::ConnectionStatus::Online => "online",
            host_client::ConnectionStatus::Probing => "probing",
            host_client::ConnectionStatus::Offline => "offline",
            host_client::ConnectionStatus::Disabled => "disabled",
            host_client::ConnectionStatus::AuthFailed => "auth-failed",
            host_client::ConnectionStatus::Unknown => "unknown",
        }
        .to_string()
    })
    .await
    .unwrap_or_else(|_| "unknown".to_string())
}

#[tauri::command]
async fn sessions(
    profile: Option<String>,
    limit: Option<usize>,
    connection_id: Option<String>,
) -> Vec<SessionEntry> {
    off_main(move || match profile {
        Some(p) => sessions_via_alp(&p, limit, connection_id.as_deref()),
        None => host_profile_names(connection_id.as_deref())
            .into_iter()
            .flat_map(|p| sessions_via_alp(&p, limit, connection_id.as_deref()))
            .collect(),
    })
    .await
    .unwrap_or_default()
}

#[tauri::command]
async fn runs_list(
    profile: String,
    limit: Option<usize>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"profile": profile, "limit": limit.unwrap_or(30)});
    off_main(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.runs.list", params),
        None => host_client::call("host.runs.list", params),
    })
    .await?
}

#[tauri::command]
async fn run_read(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"profile": profile, "id": id});
    off_main(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.run.read", params),
        None => host_client::call("host.run.read", params),
    })
    .await?
}

#[tauri::command]
async fn run_cancel(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"profile": profile, "id": id});
    off_main(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.run.cancel", params),
        None => host_client::call("host.run.cancel", params),
    })
    .await?
}

fn host_profile_names(connection_id: Option<&str>) -> Vec<String> {
    let value = host_array_value_for(
        connection_id,
        "host.profiles.list",
        serde_json::json!({}),
        "profiles",
    );
    value
        .as_array()
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter_map(|row| row.get("name").and_then(|v| v.as_str()).map(str::to_string))
        .collect()
}

fn host_array_value(method: &str, params: serde_json::Value, key: &str) -> serde_json::Value {
    host_client::call(method, params)
        .ok()
        .and_then(|v| v.get(key).cloned())
        .unwrap_or_else(|| serde_json::Value::Array(vec![]))
}

fn host_array_value_for(
    connection_id: Option<&str>,
    method: &str,
    params: serde_json::Value,
    key: &str,
) -> serde_json::Value {
    let res = match connection_id {
        Some(cid) => host_client::call_for(cid, method, params),
        None => host_client::call(method, params),
    };
    res.ok()
        .and_then(|v| v.get(key).cloned())
        .unwrap_or_else(|| serde_json::Value::Array(vec![]))
}

fn sessions_via_alp(
    profile: &str,
    limit: Option<usize>,
    connection_id: Option<&str>,
) -> Vec<SessionEntry> {
    let mut params = serde_json::json!({"profile": profile});
    if let Some(limit) = limit {
        params["limit"] = serde_json::json!(limit);
    }
    let call_result = match connection_id {
        Some(cid) => host_client::call_for(cid, "host.sessions.list", params),
        None => host_client::call("host.sessions.list", params),
    };
    let result = match call_result {
        Ok(v) => v,
        Err(_) => return vec![],
    };
    let rows = result
        .get("sessions")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut out: Vec<SessionEntry> = Vec::with_capacity(rows.len());
    for row in rows {
        let id = row.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        if id.is_empty() {
            continue;
        }
        let mtime = row.get("mtime").and_then(|v| v.as_u64()).unwrap_or(0);
        let started_at = row
            .get("started_at")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let updated_at = row
            .get("updated_at")
            .and_then(|v| v.as_f64())
            .unwrap_or_else(|| {
                if started_at > 0.0 {
                    started_at
                } else {
                    mtime as f64
                }
            });
        let model = row
            .get("model")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());
        let first_user = row
            .get("first_user")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let turn_count = row
            .get("turn_count")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as usize;
        let kind = row
            .get("kind")
            .and_then(|v| v.as_str())
            .unwrap_or("chat")
            .to_string();
        let input_tokens = row
            .get("input_tokens")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let output_tokens = row
            .get("output_tokens")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let cost_usd = row.get("cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let last_ctx_tokens = row
            .get("last_ctx_tokens")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let size_bytes = row
            .get("size_bytes")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        out.push(SessionEntry {
            id,
            profile: profile.to_string(),
            mtime,
            started_at,
            updated_at,
            size_bytes,
            first_user,
            model,
            turn_count,
            kind,
            input_tokens,
            output_tokens,
            cost_usd,
            last_ctx_tokens,
        });
    }
    out
}

#[tauri::command]
async fn session_detail(
    profile: String,
    id: String,
    after_turn: Option<u64>,
    tail_turns: Option<u64>,
    before_turn: Option<u64>,
    max_turns: Option<u64>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let mut params = serde_json::json!({"profile": profile, "id": id});
        if let Some(after) = after_turn {
            params["after_turn"] = serde_json::json!(after);
        }
        if let Some(tail) = tail_turns {
            params["tail_turns"] = serde_json::json!(tail);
        }
        if let Some(before) = before_turn {
            params["before_turn"] = serde_json::json!(before);
        }
        if let Some(max) = max_turns {
            params["max_turns"] = serde_json::json!(max);
        }
        // Full envelope: total_turns is the client's only signal that the daemon honored the slice.
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.session.read", params),
            None => host_client::call("host.session.read", params),
        }
    })
    .await?
}

#[tauri::command]
async fn sessions_delete(
    profile: String,
    ids: Vec<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"profile": profile, "ids": ids});
    tauri::async_runtime::spawn_blocking(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.sessions.delete", params),
        None => host_client::call("host.sessions.delete", params),
    })
        .await
        .map_err(|e| format!("host.sessions.delete: {e}"))?
}

#[tauri::command]
async fn workgroups(
    profile: Option<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let params = match profile {
            Some(p) => serde_json::json!({
                "profile": p,
                "include_pipeline_status": true,
            }),
            None => serde_json::json!({"include_pipeline_status": true}),
        };
        let result = match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.workgroups.list", params),
            None => host_client::call("host.workgroups.list", params),
        }?;
        Ok(result
            .get("workgroups")
            .cloned()
            .unwrap_or_else(|| serde_json::Value::Array(vec![])))
    })
    .await?
}

#[tauri::command]
async fn read_file(
    profile: Option<String>,
    rel_path: String,
    connection_id: Option<String>,
) -> Result<String, String> {
    off_main(move || {
        let mut params = serde_json::json!({"rel_path": rel_path});
        if let Some(p) = profile {
            params["profile"] = serde_json::Value::String(p);
        }
        let result = match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.profile.read_file", params),
            None => host_client::call("host.profile.read_file", params),
        }?;
        Ok(result
            .get("text")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string())
    })
    .await?
}

#[tauri::command]
async fn set_config_field(
    profile: String,
    key: String,
    value: String,
) -> Result<(), String> {
    alp_call_async(
        "host.config.set_field",
        serde_json::json!({"profile": profile, "key": key, "value": value}),
    )
    .await
}

#[tauri::command]
async fn unset_config_field(profile: String, key: String) -> Result<(), String> {
    alp_call_async(
        "host.config.unset_field",
        serde_json::json!({"profile": profile, "key": key}),
    )
    .await
}

#[tauri::command]
async fn draft_identity(profile: String) -> Result<String, String> {
    let resp = tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.identity.draft",
            serde_json::json!({"profile": profile}),
        )
    })
    .await
    .map_err(|e| format!("host.identity.draft: {e}"))??;
    resp.get("bio")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| "missing bio in response".to_string())
}

#[tauri::command]
async fn port_available(host: String, port: u16) -> bool {
    tauri::async_runtime::spawn_blocking(move || {
        let bind_host = if host.is_empty() { "127.0.0.1" } else { &host };
        std::net::TcpListener::bind((bind_host, port)).is_ok()
    })
    .await
    .unwrap_or(false)
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Supervisor {
    Launchd,
    Systemd,
    None,
}

// With a supervisor installed, ask IT to start the service — a foreground `alpi daemon start` races launchd's KeepAlive for the singleton lock.
fn daemon_start_argv(sup: Supervisor, uid: u32) -> Vec<String> {
    match sup {
        Supervisor::Launchd => vec![
            "launchctl".into(),
            "kickstart".into(),
            format!("gui/{uid}/com.alpi.daemon"),
        ],
        Supervisor::Systemd => vec![
            "systemctl".into(),
            "--user".into(),
            "start".into(),
            "alpi-daemon.service".into(),
        ],
        Supervisor::None => vec!["alpi".into(), "daemon".into(), "start".into()],
    }
}

#[cfg(unix)]
fn current_uid() -> u32 {
    extern "C" {
        fn getuid() -> u32;
    }
    unsafe { getuid() }
}
#[cfg(not(unix))]
fn current_uid() -> u32 {
    0
}

fn detect_supervisor() -> Supervisor {
    let Some(home) = std::env::var_os("HOME").map(std::path::PathBuf::from) else {
        return Supervisor::None;
    };
    if cfg!(target_os = "macos") && home.join("Library/LaunchAgents/com.alpi.daemon.plist").exists() {
        return Supervisor::Launchd;
    }
    if cfg!(target_os = "linux") && home.join(".config/systemd/user/alpi-daemon.service").exists() {
        return Supervisor::Systemd;
    }
    Supervisor::None
}

// Local subprocess: daemon may not be running yet (start/install case).
#[tauri::command]
async fn service_action(profile: String, action: String) -> Result<String, String> {
    let _ = &profile; // kept for the JS command ABI; the daemon is global, not per-profile.
    if !matches!(
        action.as_str(),
        "start" | "stop" | "restart" | "install" | "uninstall"
    ) {
        return Err(format!("invalid action: {action}"));
    }
    if action == "start" {
        return tauri::async_runtime::spawn_blocking(move || {
            let argv = daemon_start_argv(detect_supervisor(), current_uid());
            let mut child = Command::new(&argv[0])
                .args(&argv[1..])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::piped())
                .spawn()
                .map_err(|e| format!("spawn {argv:?}: {e}"))?;
            // Readiness = host.sock + a working RPC, never the pidfile (the pid is written before the socket listens).
            let mut launcher_exited = false;
            for _ in 0..240 {
                if host_client::call("host.version", serde_json::json!({})).is_ok() {
                    return Ok("started".into());
                }
                if !launcher_exited {
                    if let Ok(Some(status)) = child.try_wait() {
                        launcher_exited = true;
                        if !status.success() {
                            if host_client::call("host.version", serde_json::json!({})).is_ok() {
                                return Ok("started".into());
                            }
                            let mut err = String::new();
                            if let Some(mut s) = child.stderr.take() {
                                use std::io::Read;
                                let _ = s.read_to_string(&mut err);
                            }
                            return Err(format!("daemon start failed ({status}): {}", err.trim()));
                        }
                    }
                }
                std::thread::sleep(std::time::Duration::from_millis(50));
            }
            Err("daemon did not become reachable (host.sock + RPC) in time".into())
        })
        .await
        .map_err(|e| format!("join: {e}"))?;
    }
    let action_for_msg = action.clone();
    let action_for_wait = action.clone();
    let out = tauri::async_runtime::spawn_blocking(move || {
        Command::new("alpi")
            .args(["daemon", &action])
            .output()
    })
    .await
    .map_err(|e| format!("join: {e}"))?
    .map_err(|e| format!("spawn `alpi daemon`: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "daemon {} failed: {}",
            action_for_msg,
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    if action_for_wait == "restart" || action_for_wait == "install" {
        tauri::async_runtime::spawn_blocking(move || {
            if let Some(home) = crate::home::resolve_home(Some("default")) {
                let pid_path = home.join("service.pid");
                for _ in 0..120 {
                    if pid_path.exists() {
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(50));
                }
            }
        })
        .await
        .map_err(|e| format!("join: {e}"))?;
    }
    Ok(String::from_utf8_lossy(&out.stdout).trim().to_string())
}

#[tauri::command]
async fn email_status(profile: String, connection_id: Option<String>) -> serde_json::Value {
    off_main(move || host_array_value_for(
        connection_id.as_deref(),
        "host.email.status",
        serde_json::json!({"profile": profile}),
        "accounts",
    ))
    .await
    .unwrap_or(serde_json::Value::Array(vec![]))
}

#[tauri::command]
async fn devices_list(connection_id: Option<String>) -> serde_json::Value {
    off_main(move || host_array_value_for(
        connection_id.as_deref(),
        "host.devices.list",
        serde_json::json!({}),
        "devices",
    ))
        .await
        .unwrap_or(serde_json::Value::Array(vec![]))
}

#[tauri::command]
async fn devices_generate(
    label: String,
    role: Option<String>,
    profiles: Option<Vec<String>>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let role = role.unwrap_or_else(|| "member".into());
    let profiles = profiles.unwrap_or_default();
    let value = tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({
            "label": label, "role": role, "profiles": profiles,
        });
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.devices.generate", params),
            None => host_client::call("host.devices.generate", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(value)
}

#[tauri::command]
async fn devices_set_profiles(
    token_id: String,
    profiles: Vec<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let value = tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({"token_id": token_id, "profiles": profiles});
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.devices.set_profiles", params),
            None => host_client::call("host.devices.set_profiles", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(value)
}

#[tauri::command]
async fn devices_promote(token_id: String, connection_id: Option<String>) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({"token_id": token_id});
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.devices.promote", params),
            None => host_client::call("host.devices.promote", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
}

#[tauri::command]
async fn devices_demote(token_id: String, connection_id: Option<String>) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({"token_id": token_id});
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.devices.demote", params),
            None => host_client::call("host.devices.demote", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
}

#[tauri::command]
async fn devices_revoke(token_id: String, connection_id: Option<String>) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({"token_id": token_id});
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.devices.revoke", params),
            None => host_client::call("host.devices.revoke", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
}

#[tauri::command]
async fn devices_rename(
    token_id: String,
    label: String,
    connection_id: Option<String>,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({"token_id": token_id, "label": label});
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.devices.rename", params),
            None => host_client::call("host.devices.rename", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
}

fn connections_call(
    connection_id: Option<&str>, method: &str, params: serde_json::Value,
) -> Result<serde_json::Value, String> {
    match connection_id {
        Some(cid) => host_client::call_for(cid, method, params),
        None => host_client::call(method, params),
    }
}

#[tauri::command]
async fn connections_summary(connection_id: Option<String>) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        connections_call(connection_id.as_deref(), "host.connections.summary", serde_json::json!({}))
    }).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn connections_create(
    label: String, role: String, profiles: Vec<String>, connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        connection_id.as_deref(),
        "host.connections.create",
        serde_json::json!({"label": label, "role": role, "profiles": profiles}),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn connections_add_device(
    target_id: String, connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        connection_id.as_deref(),
        "host.connections.add_device",
        serde_json::json!({"connection_id": target_id}),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn connections_pairing_status(
    target_id: String, pairing_id: String, connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        connection_id.as_deref(),
        "host.connections.pairing_status",
        serde_json::json!({"connection_id": target_id, "pairing_id": pairing_id}),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn connections_cancel_pairing(
    target_id: String, pairing_id: String, connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        connection_id.as_deref(),
        "host.connections.cancel_pairing",
        serde_json::json!({"connection_id": target_id, "pairing_id": pairing_id}),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn connections_update(
    target_id: String, label: String, role: String, profiles: Vec<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        connection_id.as_deref(),
        "host.connections.update",
        serde_json::json!({
            "connection_id": target_id, "label": label,
            "role": role, "profiles": profiles,
        }),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn connections_set_status(
    target_id: String, status: String, connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        connection_id.as_deref(),
        "host.connections.set_status",
        serde_json::json!({"connection_id": target_id, "status": status}),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn connections_delete(
    target_id: String, connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        connection_id.as_deref(),
        "host.connections.delete",
        serde_json::json!({"connection_id": target_id}),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn connections_revoke_device(
    target_id: String, device_id: String, connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        connection_id.as_deref(),
        "host.connections.revoke_device",
        serde_json::json!({"connection_id": target_id, "device_id": device_id}),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn audit_list(
    source_connection_id: Option<String>, target_connection_id: Option<String>,
    device_id: Option<String>, result: Option<String>, cursor: Option<String>,
    limit: Option<u64>,
) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || connections_call(
        source_connection_id.as_deref(),
        "host.audit.list",
        serde_json::json!({
            "connection_id": target_connection_id.unwrap_or_default(),
            "device_id": device_id.unwrap_or_default(),
            "result": result.unwrap_or_default(),
            "cursor": cursor.unwrap_or_default(),
            "limit": limit.unwrap_or(100),
        }),
    )).await.map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn network_status() -> Result<serde_json::Value, String> {
    let value = tauri::async_runtime::spawn_blocking(|| {
        host_client::call("host.network.status", serde_json::json!({}))
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(value)
}

#[tauri::command]
async fn network_set_advertised(
    host: Option<String>,
    device_name: Option<String>,
    endpoints: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    // Only forward the fields the caller actually set — omitted keys are
    // preserved by the host RPC (host = network.host, device_name = host.device_name).
    let mut params = serde_json::Map::new();
    if let Some(h) = host {
        params.insert("host".into(), serde_json::json!(h));
    }
    if let Some(n) = device_name {
        params.insert("device_name".into(), serde_json::json!(n));
    }
    if let Some(value) = endpoints {
        params.insert("endpoints".into(), value);
    }
    let value = tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.network.set_advertised",
            serde_json::Value::Object(params),
        )
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(value)
}

#[tauri::command]
async fn network_restart_host_server() -> Result<serde_json::Value, String> {
    let value = tauri::async_runtime::spawn_blocking(|| {
        host_client::call("host.network.restart_host_server", serde_json::json!({}))
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(value)
}

#[tauri::command]
async fn profile_storage(profile: String, connection_id: Option<String>) -> serde_json::Value {
    off_main(move || host_array_value_for(
        connection_id.as_deref(),
        "host.profile.storage",
        serde_json::json!({"profile": profile}),
        "storage",
    ))
    .await
    .unwrap_or(serde_json::Value::Array(vec![]))
}

#[tauri::command]
async fn cleanup_plan(
    profile: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let res = tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({"profile": profile});
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.cleanup.plan", params),
            None => host_client::call("host.cleanup.plan", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(res
        .get("categories")
        .cloned()
        .unwrap_or_else(|| serde_json::Value::Array(vec![])))
}

#[tauri::command]
async fn cleanup_apply(
    profile: String,
    keys: Vec<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let res = tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({"profile": profile, "keys": keys});
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.cleanup.apply", params),
            None => host_client::call("host.cleanup.apply", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(res
        .get("results")
        .cloned()
        .unwrap_or_else(|| serde_json::Value::Array(vec![])))
}

#[tauri::command]
async fn workgroup_members(
    profile: String,
    wg_id: String,
    connection_id: Option<String>,
) -> serde_json::Value {
    off_main(move || host_array_value_for(
        connection_id.as_deref(),
        "host.workgroup.members",
        serde_json::json!({"profile": profile, "wg_id": wg_id}),
        "members",
    ))
    .await
    .unwrap_or(serde_json::Value::Array(vec![]))
}

#[tauri::command]
async fn workgroup_create(
    profile: String,
    name: String,
    member_peer_ids: Vec<String>,
    budget_usd: Option<f64>,
    briefing: Option<String>,
    connection_id: Option<String>,
) -> Result<String, String> {
    let mut params = serde_json::json!({
        "profile": profile,
        "name": name,
        "members": member_peer_ids,
    });
    if let Some(b) = budget_usd {
        params["budget_usd"] = serde_json::json!(b);
    }
    if let Some(b) = briefing.filter(|s| !s.is_empty()) {
        params["briefing"] = serde_json::Value::String(b);
    }
    let result = tauri::async_runtime::spawn_blocking(move || {
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.workgroup.create", params),
            None => host_client::call("host.workgroup.create", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(result
        .get("wg_id")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string())
}

#[tauri::command]
async fn workgroup_pick_recipe(
    app: tauri::AppHandle,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let picked = tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .add_filter("recipe", &["yaml", "yml"])
            .set_title("Import recipe")
            .blocking_pick_file()
    })
    .await
    .map_err(|e| format!("join: {e}"))?;
    let path = match picked.and_then(|f| f.into_path().ok()) {
        Some(p) => p,
        None => return Ok(serde_json::Value::Null),
    };
    let recipe_id = path
        .file_stem()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default();
    let yaml = std::fs::read_to_string(&path).map_err(|e| format!("read {}: {e}", path.display()))?;
    let describe_params = serde_json::json!({ "yaml": yaml, "recipe_id": recipe_id });
    let cid = connection_id.clone();
    let meta = tauri::async_runtime::spawn_blocking(move || match cid.as_deref() {
        Some(c) => host_client::call_for(c, "host.workgroup.recipes.describe", describe_params),
        None => host_client::call("host.workgroup.recipes.describe", describe_params),
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(serde_json::json!({ "yaml": yaml, "recipe_id": recipe_id, "meta": meta }))
}

#[tauri::command]
async fn workgroup_saved_recipes(
    profile: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({ "profile": profile });
    tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.workgroup.recipes.list", params),
        None => host_client::call("host.workgroup.recipes.list", params),
    })
    .await
    .map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn workgroup_launch_recipe(
    profile: String,
    yaml: Option<String>,
    recipe_id: Option<String>,
    params: serde_json::Value,
    briefing: Option<String>,
    inputs: Option<serde_json::Value>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut p = serde_json::json!({
        "profile": profile,
        "recipe_id": recipe_id.unwrap_or_else(|| "recipe".to_string()),
        "params": params,
    });
    if let Some(y) = yaml {
        p["yaml"] = serde_json::Value::String(y);
    }
    if let Some(b) = briefing {
        p["briefing"] = serde_json::Value::String(b);
    }
    if let Some(v) = inputs {
        p["inputs"] = v;
    }
    tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.workgroup.launch_recipe", p),
        None => host_client::call("host.workgroup.launch_recipe", p),
    })
    .await
    .map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn workgroup_update(
    profile: String,
    wg_id: String,
    briefing: Option<String>,
    budget_usd: Option<f64>,
    clear_budget: Option<bool>,
    auto_read: Option<bool>,
    connection_id: Option<String>,
) -> Result<(), String> {
    let mut params = serde_json::json!({ "profile": profile, "wg_id": wg_id });
    if let Some(b) = briefing {
        params["briefing"] = serde_json::Value::String(b);
    }
    if let Some(a) = auto_read {
        params["auto_read"] = serde_json::json!(a);
    }
    if clear_budget.unwrap_or(false) {
        params["clear_budget"] = serde_json::json!(true);
    } else if let Some(b) = budget_usd {
        params["budget_usd"] = serde_json::json!(b);
    }
    tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.workgroup.update", params),
        None => host_client::call("host.workgroup.update", params),
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
}

#[tauri::command]
async fn workgroup_add_member(
    profile: String,
    wg_id: String,
    member: String,
    connection_id: Option<String>,
) -> Result<(), String> {
    let params = serde_json::json!({ "profile": profile, "wg_id": wg_id, "member": member });
    tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.workgroup.add_member", params),
        None => host_client::call("host.workgroup.add_member", params),
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
}

#[tauri::command]
async fn workgroup_action(
    profile: String,
    wg_id: String,
    action: String,
    member_pubkey: Option<String>,
    connection_id: Option<String>,
) -> Result<String, String> {
    let (method, params) = match action.as_str() {
        "pause" | "resume" | "leave" => (
            "host.workgroup.action",
            serde_json::json!({ "profile": profile, "wg_id": wg_id, "action": action }),
        ),
        "kick" => (
            "host.workgroup.kick",
            serde_json::json!({
                "profile": profile,
                "wg_id": wg_id,
                "member": member_pubkey.unwrap_or_default(),
            }),
        ),
        "remove" => (
            "host.workgroup.remove",
            serde_json::json!({ "profile": profile, "wg_id": wg_id }),
        ),
        _ => return Err(format!("invalid action: {action}")),
    };
    tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, method, params),
        None => host_client::call(method, params),
    })
        .await
        .map_err(|e| format!("join: {e}"))??;
    Ok(String::new())
}

#[derive(Serialize)]
struct PeerProbe {
    id: String,
    status: String,
    reason: Option<String>,
}

#[derive(Serialize)]
struct GatewayProbe {
    name: String,
    status: String,
    reason: Option<String>,
}

#[tauri::command]
async fn probe_email(
    profile: String,
    only: Option<Vec<String>>,
    connection_id: Option<String>,
) -> Vec<GatewayProbe> {
    let ids: Vec<String> = only.unwrap_or_default();
    let mut handles = vec![];
    for id in ids {
        let p = profile.clone();
        let account_id = id.clone();
        let cid = connection_id.clone();
        handles.push(tauri::async_runtime::spawn_blocking(move || {
            let params = serde_json::json!({ "profile": p, "id": account_id.clone() });
            let result = match cid.as_deref() {
                Some(c) => host_client::call_for(c, "host.email.probe", params),
                None => host_client::call("host.email.probe", params),
            };
            let (status, reason) = match result {
                Ok(v) => (
                    v.get("status").and_then(|x| x.as_str()).unwrap_or("off").to_string(),
                    v.get("reason").and_then(|x| x.as_str()).map(|x| x.to_string()),
                ),
                Err(_) => ("off".to_string(), None),
            };
            GatewayProbe {
                name: account_id,
                status,
                reason,
            }
        }));
    }
    let mut out = vec![];
    for h in handles {
        if let Ok(p) = h.await {
            out.push(p);
        }
    }
    out
}

#[tauri::command]
async fn probe_peers(profile: String, ids: Vec<String>) -> Vec<PeerProbe> {
    let mut handles = vec![];
    for id in ids {
        let p = profile.clone();
        let id_owned = id.clone();
        handles.push(tauri::async_runtime::spawn_blocking(move || {
            let result = host_client::call(
                "host.peers.ping",
                serde_json::json!({ "profile": p, "peer_id": id_owned.clone() }),
            );
            let (status, reason) = match result {
                Ok(v) => (
                    v.get("status").and_then(|x| x.as_str()).unwrap_or("off").to_string(),
                    v.get("reason").and_then(|x| x.as_str()).map(|x| x.to_string()),
                ),
                Err(e) => ("off".to_string(), Some(e)),
            };
            PeerProbe {
                id: id_owned,
                status,
                reason,
            }
        }));
    }
    let mut out = vec![];
    for h in handles {
        if let Ok(p) = h.await {
            out.push(p);
        }
    }
    out
}

#[tauri::command]
async fn peer_add(
    profile: String,
    peer_id: String,
    pubkey: String,
    address: Option<String>,
    alias: Option<String>,
    allow: Option<String>,
) -> Result<(), String> {
    let allow_list: Vec<String> = allow
        .as_deref()
        .filter(|s| !s.is_empty())
        .map(|s| s.split(',').map(|x| x.trim().to_string()).collect())
        .unwrap_or_else(|| vec!["link.ping".into(), "link.ask".into()]);
    let mut params = serde_json::json!({
        "profile": profile,
        "id": peer_id,
        "pubkey": pubkey,
        "allow": allow_list,
    });
    if let Some(a) = address.filter(|s| !s.is_empty()) {
        params["address"] = serde_json::Value::String(a);
    }
    if let Some(a) = alias.filter(|s| !s.is_empty()) {
        params["alias"] = serde_json::Value::String(a);
    }
    alp_call_async("host.peers.add", params).await
}

#[tauri::command]
async fn email_config(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> serde_json::Value {
    off_main(move || {
        let params = serde_json::json!({"profile": profile, "id": id});
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for(cid, "host.email.config", params),
            None => host_client::call("host.email.config", params),
        }
        .ok()
        .and_then(|v| v.get("config").cloned())
        .unwrap_or(serde_json::Value::Null)
    })
    .await
    .unwrap_or(serde_json::Value::Null)
}

// Gmail OAuth — the loopback HTTP server lives on the **client** (this
// desktop process), never on the daemon. The daemon may be remote and
// headless; only the client machine has a browser. We:
//   1. Bind a TCP socket on 127.0.0.1:<random> here.
//   2. Ask the daemon to prepare the consent URL with that redirect.
//   3. Open the URL in the system browser.
//   4. Accept ONE GET, parse code+state from the query.
//   5. Hand them back to the daemon for the token exchange.
//
fn emit_gmail_event(
    app: &AppHandle,
    flow_id: &str,
    connection_id: &Option<String>,
    mut payload: serde_json::Value,
) {
    if let Some(map) = payload.as_object_mut() {
        map.insert("flow_id".into(), serde_json::Value::String(flow_id.to_string()));
        map.insert(
            "connection_id".into(),
            serde_json::to_value(connection_id).unwrap_or(serde_json::Value::Null),
        );
    }
    let _ = app.emit("gmail-auth-event", payload);
}

#[tauri::command]
async fn email_gmail_authorize(
    app: AppHandle,
    profile: String,
    address: String,
    client_id: String,
    client_secret: String,
    flow_id: String,
    connection_id: Option<String>,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        run_gmail_oauth(
            app,
            profile,
            address,
            client_id,
            client_secret,
            flow_id,
            connection_id,
        )
    })
    .await
    .map_err(|e| format!("join: {e}"))?;
    Ok(())
}

fn run_gmail_oauth(
    app: AppHandle,
    profile: String,
    address: String,
    client_id: String,
    client_secret: String,
    flow_id: String,
    connection_id: Option<String>,
) {
    use std::io::{ErrorKind, Read, Write};
    use std::net::TcpListener;
    use std::time::{Duration, Instant};

    let emit_err = |text: String| {
        emit_gmail_event(
            &app,
            &flow_id,
            &connection_id,
            serde_json::json!({"event": "error", "text": text}),
        );
    };
    let host_call = |method: &str, params: serde_json::Value| match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, method, params),
        None => host_client::call(method, params),
    };

    // 1. Bind the loopback first so we can advertise the exact port we'll
    //    be listening on. Port-0 lets the OS pick one; we never reserve.
    let listener = match TcpListener::bind("127.0.0.1:0") {
        Ok(l) => l,
        Err(e) => return emit_err(format!("cannot bind loopback: {e}")),
    };
    let port = match listener.local_addr() {
        Ok(addr) => addr.port(),
        Err(e) => return emit_err(format!("cannot resolve loopback port: {e}")),
    };
    let redirect_uri = format!("http://127.0.0.1:{port}");

    // 2. Ask the daemon to persist creds + prepare the consent URL.
    let begin_resp = match host_call(
        "host.email.gmail.begin",
        serde_json::json!({
            "profile": profile,
            "address": address,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }),
    ) {
        Ok(v) => v,
        Err(e) => return emit_err(format!("daemon refused gmail.begin: {e}")),
    };
    let auth_url = begin_resp
        .get("auth_url")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .unwrap_or_default();
    let state = begin_resp
        .get("state")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .unwrap_or_default();
    if auth_url.is_empty() || state.is_empty() {
        return emit_err("daemon returned no auth_url/state".into());
    }

    // 3. Launch the browser. If this fails we still wait for the user to
    //    paste the URL manually (the JS modal also shows the URL).
    let _ = open_in_browser(&auth_url);
    emit_gmail_event(
        &app,
        &flow_id,
        &connection_id,
        serde_json::json!({"event": "browser_opened", "auth_url": auth_url}),
    );

    // 4. Accept exactly one inbound and read the GET request.
    // 300s matches the daemon's pending-state TTL. ``set_read_timeout``
    // doesn't apply until AFTER ``accept`` returns, so without an
    // explicit deadline a user who never finishes consent (closes the
    // tab, Google never redirects) would hang this thread forever.
    let _ = listener.set_ttl(64);
    if let Err(e) = listener.set_nonblocking(true) {
        return emit_err(format!("listener config failed: {e}"));
    }
    let deadline = Instant::now() + Duration::from_secs(_OAUTH_ACCEPT_TIMEOUT_SECS);
    let (mut stream, _peer) = loop {
        match listener.accept() {
            Ok(pair) => break pair,
            Err(ref e) if e.kind() == ErrorKind::WouldBlock => {
                if Instant::now() >= deadline {
                    return emit_err(
                        "OAuth timed out: no callback received in 5 min — restart the flow".into(),
                    );
                }
                std::thread::sleep(Duration::from_millis(200));
            }
            Err(e) => return emit_err(format!("loopback accept failed: {e}")),
        }
    };
    // Block-mode again for the single read; we already gated the accept above.
    let _ = stream.set_nonblocking(false);
    let _ = stream.set_read_timeout(Some(Duration::from_secs(_OAUTH_READ_TIMEOUT_SECS)));
    let mut buf = [0u8; 2048];
    let n = match stream.read(&mut buf) {
        Ok(n) => n,
        Err(e) => return emit_err(format!("loopback read failed: {e}")),
    };
    let request_line = std::str::from_utf8(&buf[..n])
        .ok()
        .and_then(|s| s.lines().next())
        .unwrap_or("")
        .to_string();
    let path = request_line.split_whitespace().nth(1).unwrap_or("");
    let (got_code, got_state, got_err) = parse_oauth_callback(path);

    // 5. Close the browser tab with a friendly page no matter what.
    let body = if got_err.is_empty() && !got_code.is_empty() {
        "<h1>alpi — Gmail authorized</h1><p>You can close this tab and return to alpi.</p>"
    } else {
        "<h1>alpi — Gmail authorization failed</h1><p>Return to alpi for details.</p>"
    };
    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        body.len(),
        body,
    );
    let _ = stream.write_all(response.as_bytes());
    let _ = stream.flush();
    drop(stream);
    drop(listener);

    if !got_err.is_empty() {
        return emit_err(format!("Google denied consent: {got_err}"));
    }
    if got_code.is_empty() {
        return emit_err("no `code` returned by Google (consent cancelled?)".into());
    }
    if got_state != state {
        return emit_err("OAuth state mismatch — possible CSRF or stale flow".into());
    }

    // 6. Hand the code to the daemon for the token exchange.
    let exchange = match host_call(
        "host.email.gmail.exchange",
        serde_json::json!({"state": state, "code": got_code}),
    ) {
        Ok(v) => v,
        Err(e) => return emit_err(format!("token exchange failed: {e}")),
    };
    let email = exchange
        .get("email")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    emit_gmail_event(
        &app,
        &flow_id,
        &connection_id,
        serde_json::json!({"event": "authorized", "email": email}),
    );
}

const _OAUTH_READ_TIMEOUT_SECS: u64 = 30;
const _OAUTH_ACCEPT_TIMEOUT_SECS: u64 = 300;

// Paste fallback for cross-machine setups (SSH X-forwarding, VNC,
// Tauri inside a VM, …) where the desktop process and the user's
// browser don't share a 127.0.0.1. The user opens the consent URL
// on whatever device has their browser, copies the failed redirect
// URL from the address bar, pastes it back here. We parse code+state
// and call exchange directly — same daemon endpoint the loopback
// path uses, no new architecture.
#[tauri::command]
async fn email_gmail_paste(
    app: AppHandle,
    pasted_url: String,
    flow_id: String,
    connection_id: Option<String>,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let emit_err = |text: String| {
            emit_gmail_event(
                &app,
                &flow_id,
                &connection_id,
                serde_json::json!({"event": "error", "text": text}),
            );
        };

        let (code, state, error) = parse_oauth_callback_input(&pasted_url);
        if !error.is_empty() {
            return emit_err(format!("Google denied consent: {error}"));
        }
        if code.is_empty() {
            return emit_err(
                "no `code` parameter found in pasted URL — copy the FULL redirect URL from your browser's address bar"
                    .into(),
            );
        }
        if state.is_empty() {
            return emit_err(
                "no `state` parameter found in pasted URL — the link is malformed".into(),
            );
        }

        let exchange_params = serde_json::json!({"state": state, "code": code});
        let result = match connection_id.as_deref() {
            Some(cid) => {
                host_client::call_for(cid, "host.email.gmail.exchange", exchange_params)
            }
            None => host_client::call("host.email.gmail.exchange", exchange_params),
        };
        match result {
            Ok(v) => {
                let email = v
                    .get("email")
                    .and_then(|e| e.as_str())
                    .unwrap_or("")
                    .to_string();
                emit_gmail_event(
                    &app,
                    &flow_id,
                    &connection_id,
                    serde_json::json!({"event": "authorized", "email": email}),
                );
            }
            Err(e) => emit_err(format!("token exchange failed: {e}")),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))?;
    Ok(())
}

fn parse_oauth_callback(path: &str) -> (String, String, String) {
    let query = path.split_once('?').map(|(_, q)| q).unwrap_or("");
    let mut code = String::new();
    let mut state = String::new();
    let mut error = String::new();
    for pair in query.split('&') {
        let (k, v) = match pair.split_once('=') {
            Some(kv) => kv,
            None => continue,
        };
        let decoded = percent_decode(v);
        match k {
            "code" => code = decoded,
            "state" => state = decoded,
            "error" => error = decoded,
            _ => {}
        }
    }
    (code, state, error)
}

// Same query parser, but tolerates the user pasting a full URL
// (``http://127.0.0.1:55989/?code=…``) — the paste fallback in the
// desktop modal accepts whatever the user copies from their browser
// bar, including the scheme + host they can't reach.
fn parse_oauth_callback_input(input: &str) -> (String, String, String) {
    let trimmed = input.trim();
    let path_query = if let Some((_, after_scheme)) = trimmed.split_once("://") {
        match after_scheme.find('/') {
            Some(slash) => &after_scheme[slash..],
            None => "/",
        }
    } else {
        trimmed
    };
    parse_oauth_callback(path_query)
}

fn percent_decode(s: &str) -> String {
    // Minimal %XX + '+' decoder for OAuth query params (ASCII-only fields).
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        let b = bytes[i];
        if b == b'+' {
            out.push(b' ');
            i += 1;
        } else if b == b'%' && i + 2 < bytes.len() {
            let hi = (bytes[i + 1] as char).to_digit(16);
            let lo = (bytes[i + 2] as char).to_digit(16);
            if let (Some(h), Some(l)) = (hi, lo) {
                out.push(((h << 4) | l) as u8);
                i += 3;
            } else {
                out.push(b);
                i += 1;
            }
        } else {
            out.push(b);
            i += 1;
        }
    }
    String::from_utf8(out).unwrap_or_default()
}

fn open_in_browser(url: &str) -> std::io::Result<()> {
    #[cfg(target_os = "macos")]
    let mut cmd = Command::new("open");
    #[cfg(target_os = "linux")]
    let mut cmd = Command::new("xdg-open");
    #[cfg(target_os = "windows")]
    let mut cmd = {
        let mut c = Command::new("cmd");
        c.args(["/C", "start", ""]);
        c
    };
    cmd.arg(url).stdout(Stdio::null()).stderr(Stdio::null()).spawn()?;
    Ok(())
}

#[tauri::command]
async fn email_remove(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> Result<(), String> {
    alp_call_async_for(
        connection_id,
        "host.email.remove",
        serde_json::json!({"profile": profile, "id": id}),
    )
    .await
}

#[tauri::command]
async fn email_add(
    profile: String,
    address: String,
    password: String,
    imap_host: String,
    smtp_host: String,
    imap_port: Option<String>,
    smtp_port: Option<String>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut params = serde_json::json!({
        "profile": profile,
        "address": address,
        "password": password,
        "imap_host": imap_host,
        "smtp_host": smtp_host,
    });
    if let Some(p) = imap_port.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
        params["imap_port"] = serde_json::Value::String(p.to_string());
    }
    if let Some(p) = smtp_port.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
        params["smtp_port"] = serde_json::Value::String(p.to_string());
    }
    tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.email.add", params),
        None => host_client::call("host.email.add", params),
    })
    .await
    .map_err(|e| format!("host.email.add: {e}"))?
}

#[tauri::command]
async fn mcp_add(
    profile: String,
    name: String,
    command: String,
    args: String,
    env: Vec<String>,
    connection_id: Option<String>,
) -> Result<(), String> {
    let args_vec: Vec<String> = if args.trim().is_empty() {
        vec![]
    } else {
        match shellwords_split(&args) {
            Ok(v) => v,
            Err(e) => return Err(format!("invalid args: {e}")),
        }
    };
    let mut env_map = serde_json::Map::new();
    for pair in env {
        if let Some((k, v)) = pair.split_once('=') {
            env_map.insert(k.trim().to_string(), serde_json::Value::String(v.trim().to_string()));
        }
    }
    alp_call_async_for(
        connection_id,
        "host.mcp.add",
        serde_json::json!({
            "profile": profile,
            "name": name,
            "command": command,
            "args": args_vec,
            "env": env_map,
        }),
    )
    .await
}

#[tauri::command]
async fn mcp_remove(
    profile: String, name: String, connection_id: Option<String>,
) -> Result<(), String> {
    alp_call_async_for(
        connection_id,
        "host.mcp.remove",
        serde_json::json!({"profile": profile, "name": name}),
    )
    .await
}

#[tauri::command]
async fn profile_mcp_tools(
    profile: String, name: String, connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    off_main(move || {
        let params = serde_json::json!({ "profile": profile, "name": name });
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.mcp.tools", params),
            None => host_client::call("host.mcp.tools", params),
        }
        .map(|v| {
            v.get("tools")
                .cloned()
                .unwrap_or_else(|| serde_json::Value::Array(vec![]))
        })
        .map_err(|e| e.to_string())
    })
    .await?
}

fn shellwords_split(s: &str) -> Result<Vec<String>, String> {
    let mut out: Vec<String> = vec![];
    let mut cur = String::new();
    let mut in_single = false;
    let mut in_double = false;
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '\\' if !in_single => {
                if let Some(n) = chars.next() {
                    cur.push(n);
                }
            }
            '\'' if !in_double => in_single = !in_single,
            '"' if !in_single => in_double = !in_double,
            c if c.is_whitespace() && !in_single && !in_double => {
                if !cur.is_empty() {
                    out.push(std::mem::take(&mut cur));
                }
            }
            c => cur.push(c),
        }
    }
    if in_single || in_double {
        return Err("unterminated quote".into());
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    Ok(out)
}

#[tauri::command]
async fn voice_set_voice(profile: String, voice_id: String) -> Result<(), String> {
    alp_call_async(
        "host.voice.set_voice",
        serde_json::json!({"profile": profile, "voice_id": voice_id}),
    )
    .await
}

#[tauri::command]
async fn voice_set_auto_read(profile: String, enabled: bool) -> Result<(), String> {
    alp_call_async(
        "host.voice.set_auto_read",
        serde_json::json!({"profile": profile, "enabled": enabled}),
    )
    .await
}

#[tauri::command]
async fn sandbox_set(profile: String, state: String) -> Result<(), String> {
    alp_call_async(
        "host.sandbox.set",
        serde_json::json!({"profile": profile, "state": state}),
    )
    .await
}

#[tauri::command]
async fn sandbox_network(profile: String, state: String) -> Result<(), String> {
    alp_call_async(
        "host.sandbox.network",
        serde_json::json!({"profile": profile, "state": state}),
    )
    .await
}

async fn alp_call_async(method: &'static str, params: serde_json::Value) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || host_client::call(method, params))
        .await
        .map_err(|e| format!("{method}: {e}"))?
        .map(|_| ())
}

async fn alp_call_async_for(
    connection_id: Option<String>,
    method: &'static str,
    params: serde_json::Value,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, method, params),
        None => host_client::call(method, params),
    })
    .await
    .map_err(|e| format!("{method}: {e}"))?
    .map(|_| ())
}

#[tauri::command]
async fn provider_set_key(
    profile: String, key: String, value: String, connection_id: Option<String>,
) -> Result<(), String> {
    alp_call_async_for(
        connection_id,
        "host.providers.set_key",
        serde_json::json!({"profile": profile, "key": key, "value": value}),
    )
    .await
}

#[tauri::command]
async fn provider_unset_key(
    profile: String,
    key: String,
    connection_id: Option<String>,
) -> Result<(), String> {
    alp_call_async_for(
        connection_id,
        "host.providers.unset_key",
        serde_json::json!({"profile": profile, "key": key}),
    )
    .await
}

#[tauri::command]
async fn provider_add_openrouter_model(
    profile: String, model: String,
) -> Result<(), String> {
    alp_call_async(
        "host.providers.add_openrouter_model",
        serde_json::json!({"profile": profile, "model": model}),
    )
    .await
}

#[tauri::command]
async fn provider_remove_openrouter_model(
    profile: String, model: String,
) -> Result<(), String> {
    alp_call_async(
        "host.providers.remove_openrouter_model",
        serde_json::json!({"profile": profile, "model": model}),
    )
    .await
}

#[tauri::command]
async fn provider_add_ollama(
    profile: String, name: String, url: String,
) -> Result<(), String> {
    alp_call_async(
        "host.providers.add_ollama",
        serde_json::json!({"profile": profile, "name": name, "url": url}),
    )
    .await
}

#[tauri::command]
async fn provider_remove_ollama(profile: String, name: String) -> Result<(), String> {
    alp_call_async(
        "host.providers.remove_ollama",
        serde_json::json!({"profile": profile, "name": name}),
    )
    .await
}

#[tauri::command]
async fn profile_create(name: String) -> Result<(), String> {
    alp_call_async("host.profile.create", serde_json::json!({"name": name})).await
}

#[tauri::command]
async fn profile_delete(name: String) -> Result<(), String> {
    alp_call_async("host.profile.delete", serde_json::json!({"name": name})).await
}

#[tauri::command]
async fn peer_remove(profile: String, peer_id: String) -> Result<(), String> {
    alp_call_async(
        "host.peers.remove",
        serde_json::json!({"profile": profile, "id": peer_id}),
    )
    .await
}

#[tauri::command]
async fn peers_pending_list(profile: String) -> Result<serde_json::Value, String> {
    let result = tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.peers.pending_list",
            serde_json::json!({"profile": profile}),
        )
    })
    .await
    .map_err(|e| format!("peers_pending_list: {e}"))??;
    Ok(result.get("pending").cloned().unwrap_or(serde_json::Value::Array(vec![])))
}

#[tauri::command]
async fn peers_pending_accept(
    profile: String,
    peer_id: String,
    pubkey: String,
) -> Result<(), String> {
    alp_call_async(
        "host.peers.pending_accept",
        serde_json::json!({
            "profile": profile,
            "id": peer_id,
            "pubkey": pubkey,
        }),
    )
    .await
}

#[tauri::command]
async fn peers_pending_discard(
    profile: String,
    pubkey: String,
) -> Result<(), String> {
    alp_call_async(
        "host.peers.pending_discard",
        serde_json::json!({"profile": profile, "pubkey": pubkey}),
    )
    .await
}

#[tauri::command]
async fn schedules(
    profile: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"profile": profile});
    let result = tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.schedule.list", params),
        None => host_client::call("host.schedule.list", params),
    })
    .await
    .map_err(|e| format!("schedules: {e}"))??;
    Ok(result.get("jobs").cloned().unwrap_or(serde_json::Value::Array(vec![])))
}

#[tauri::command]
async fn schedule_remove(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> Result<(), String> {
    alp_call_async_for(
        connection_id,
        "host.schedule.remove",
        serde_json::json!({"profile": profile, "id": id}),
    )
    .await
}

#[tauri::command]
async fn schedule_set_paused(
    profile: String,
    id: String,
    paused: bool,
    connection_id: Option<String>,
) -> Result<(), String> {
    alp_call_async_for(
        connection_id,
        "host.schedule.set_paused",
        serde_json::json!({"profile": profile, "id": id, "paused": paused}),
    )
    .await
}

#[tauri::command]
async fn schedule_fire(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> Result<(), String> {
    alp_call_async_for(
        connection_id,
        "host.schedule.fire",
        serde_json::json!({"profile": profile, "id": id}),
    )
    .await
}

#[tauri::command]
async fn daemon_restart(connection_id: String) -> Result<(), String> {
    alp_call_async_for(
        Some(connection_id),
        "host.daemon.restart",
        serde_json::json!({}),
    )
    .await
}

#[tauri::command]
async fn daemon_update(connection_id: String) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call_for_update(
            &connection_id,
            "host.daemon.update",
            serde_json::json!({}),
        )
    })
    .await
    .map_err(|e| format!("daemon_update: {e}"))?
}

#[tauri::command]
async fn outputs_list(
    profile: String,
    status: Option<String>,
    limit: Option<u32>,
    connection_id: Option<String>,
    all: Option<bool>,
) -> Result<serde_json::Value, String> {
    let aggregate = all == Some(true);
    let mut params = if aggregate {
        serde_json::json!({"all": true})
    } else {
        serde_json::json!({"profile": profile})
    };
    if let Some(s) = status {
        params["status"] = serde_json::Value::String(s);
    }
    if let Some(l) = limit {
        params["limit"] = serde_json::Value::Number(serde_json::Number::from(l));
    }
    let result = tauri::async_runtime::spawn_blocking(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.outputs.list", params),
        None => host_client::call("host.outputs.list", params),
    })
    .await
    .map_err(|e| format!("outputs_list: {e}"))??;
    if aggregate {
        // Pass the reply through whole: `aggregate: true` is the capability marker the JS probes to fall back on pre-aggregate daemons.
        return Ok(result);
    }
    Ok(result
        .get("outputs")
        .cloned()
        .unwrap_or(serde_json::Value::Array(vec![])))
}

#[tauri::command]
async fn outputs_read(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"profile": profile, "id": id});
    let result = tauri::async_runtime::spawn_blocking(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.outputs.read", params),
        None => host_client::call("host.outputs.read", params),
    })
    .await
    .map_err(|e| format!("outputs_read: {e}"))??;
    Ok(result.get("output").cloned().unwrap_or(serde_json::Value::Null))
}

#[tauri::command]
async fn outputs_mark_read(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"profile": profile, "id": id});
    let result = tauri::async_runtime::spawn_blocking(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.outputs.mark_read", params),
        None => host_client::call("host.outputs.mark_read", params),
    })
    .await
    .map_err(|e| format!("outputs_mark_read: {e}"))??;
    Ok(result.get("output").cloned().unwrap_or(serde_json::Value::Null))
}

#[tauri::command]
async fn outputs_mark_all_read(
    profile: String,
    connection_id: Option<String>,
) -> Result<u64, String> {
    let params = serde_json::json!({"profile": profile});
    let result = tauri::async_runtime::spawn_blocking(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.outputs.mark_all_read", params),
        None => host_client::call("host.outputs.mark_all_read", params),
    })
    .await
    .map_err(|e| format!("outputs_mark_all_read: {e}"))??;
    Ok(result.get("count").and_then(|v| v.as_u64()).unwrap_or(0))
}

#[tauri::command]
async fn outputs_delete(
    profile: String,
    id: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({"profile": profile, "id": id});
    let result = tauri::async_runtime::spawn_blocking(move || match connection_id {
        Some(cid) => host_client::call_for(&cid, "host.outputs.delete", params),
        None => host_client::call("host.outputs.delete", params),
    })
    .await
    .map_err(|e| format!("outputs_delete: {e}"))??;
    Ok(result)
}

#[tauri::command]
async fn approval_respond(request_id: String, choice: String) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({ "request_id": request_id, "choice": choice });
    let result = tauri::async_runtime::spawn_blocking(move || {
        host_client::call("host.approval.respond", params)
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(result)
}

#[tauri::command]
async fn approval_pending() -> Result<serde_json::Value, String> {
    let result = tauri::async_runtime::spawn_blocking(move || {
        host_client::call("host.approval.pending", serde_json::json!({}))
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(result)
}

#[tauri::command]
async fn clarification_respond(
    request_id: String, choice: String,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({ "request_id": request_id, "choice": choice });
    let result = tauri::async_runtime::spawn_blocking(move || {
        host_client::call("host.clarification.respond", params)
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(result)
}

#[tauri::command]
async fn clarification_pending() -> Result<serde_json::Value, String> {
    let result = tauri::async_runtime::spawn_blocking(move || {
        host_client::call("host.clarification.pending", serde_json::json!({}))
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(result)
}

#[tauri::command]
async fn resolve_ctx_window(
    profile: String,
    model: String,
    connection_id: Option<String>,
) -> Result<u64, String> {
    let result = tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({ "profile": profile, "model": model });
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.model.ctx_window", params),
            None => host_client::call("host.model.ctx_window", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(result
        .get("ctx_window")
        .and_then(|v| v.as_u64())
        .unwrap_or(0))
}

#[tauri::command]
async fn pick_folder(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let picked = tauri::async_runtime::spawn_blocking(move || {
        app.dialog().file().set_title("Select workspace").blocking_pick_folder()
    })
    .await
    .map_err(|e| format!("join: {e}"))?;
    Ok(picked
        .and_then(|f| f.into_path().ok())
        .map(|p| p.to_string_lossy().into_owned()))
}

#[derive(serde::Serialize)]
struct AttachmentMeta {
    path: String,
    name: String,
    size: u64,
}

// Returns absolute paths; the daemon validates type/size.
#[tauri::command]
async fn pick_files(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    let picked = tauri::async_runtime::spawn_blocking(move || {
        app.dialog().file().set_title("Attach files").blocking_pick_files()
    })
    .await
    .map_err(|e| format!("join: {e}"))?;
    Ok(picked
        .unwrap_or_default()
        .into_iter()
        .filter_map(|f| f.into_path().ok())
        .map(|p| p.to_string_lossy().into_owned())
        .collect())
}

// Stat the given paths (used by the picker + drag-drop) so the composer can
// render file chips with name + size before sending.
#[tauri::command]
async fn attachment_meta(paths: Vec<String>) -> Vec<AttachmentMeta> {
    off_main(move || {
        paths
            .into_iter()
            .filter_map(|p| {
                let path = std::path::Path::new(&p);
                let md = std::fs::metadata(path).ok()?;
                if !md.is_file() {
                    return None;
                }
                let name = path.file_name()?.to_string_lossy().to_string();
                Some(AttachmentMeta { path: p.clone(), name, size: md.len() })
            })
            .collect()
    })
    .await
    .unwrap_or_default()
}

#[tauri::command]
async fn save_text_file(name: String, content: String, dest: String) -> Result<AttachmentMeta, String> {
    off_main(move || -> Result<AttachmentMeta, String> {
        let base = std::path::Path::new(&name)
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .filter(|n| !n.is_empty())
            .unwrap_or_else(|| "notification.md".into());
        let dir = if dest == "download" {
            dirs::download_dir().ok_or_else(|| "no download directory".to_string())?
        } else {
            let stamp = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0);
            let sub = std::env::temp_dir().join(format!("alpi-attach-{stamp}"));
            std::fs::create_dir_all(&sub).map_err(|e| format!("mkdir: {e}"))?;
            sub
        };
        let mut path = dir.join(&base);
        if dest == "download" {
            let p = std::path::Path::new(&base);
            let stem = p.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "notification".into());
            let ext = p.extension().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "md".into());
            let mut n = 1;
            while path.exists() {
                path = dir.join(format!("{stem} ({n}).{ext}"));
                n += 1;
            }
        }
        std::fs::write(&path, content.as_bytes()).map_err(|e| format!("write: {e}"))?;
        let size = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(content.len() as u64);
        let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or(base);
        Ok(AttachmentMeta { path: path.to_string_lossy().into_owned(), name, size })
    })
    .await?
}

// Allowed read/copy roots; `extra` is the active profile's workspace (UI-supplied, trusted).
fn path_within_allowed(path: &str, extra: &[String]) -> bool {
    let canon = match std::fs::canonicalize(path) {
        Ok(c) => c,
        Err(_) => return false,
    };
    let mut roots: Vec<std::path::PathBuf> = vec![
        std::env::temp_dir(),
        std::path::PathBuf::from("/tmp"),
        std::path::PathBuf::from("/private/tmp"),
    ];
    if let Ok(h) = std::env::var("ALPI_HOME") {
        if !h.is_empty() {
            roots.push(std::path::PathBuf::from(h));
        }
    }
    if let Some(home) = dirs::home_dir() {
        roots.push(home.join(".alpi"));
    }
    for r in extra {
        if !r.is_empty() {
            roots.push(std::path::PathBuf::from(r));
        }
    }
    roots
        .iter()
        .filter_map(|r| std::fs::canonicalize(r).ok())
        .any(|rc| canon.starts_with(&rc))
}

#[tauri::command]
async fn attachment_thumb(path: String, mime: String, roots: Option<Vec<String>>) -> Option<String> {
    off_main(move || {
        use base64::Engine;
        const MAX_THUMB_BYTES: u64 = 6 * 1024 * 1024;
        if !path_within_allowed(&path, &roots.unwrap_or_default()) {
            return None;
        }
        let p = std::path::Path::new(&path);
        let md = std::fs::metadata(p).ok()?;
        if !md.is_file() || md.len() > MAX_THUMB_BYTES || !mime.starts_with("image/") {
            return None;
        }
        let bytes = std::fs::read(p).ok()?;
        let b64 = base64::engine::general_purpose::STANDARD.encode(&bytes);
        Some(format!("data:{mime};base64,{b64}"))
    })
    .await
    .ok()
    .flatten()
}

// Must stay in sync with alpi/attachments.py MAX_FILE_BYTES / MAX_TEXT_FILE_BYTES / TEXT_MIMES.
const ATTACHMENT_MAX_FILE_BYTES: u64 = 20 * 1024 * 1024;
const ATTACHMENT_MAX_TEXT_BYTES: u64 = 2 * 1024 * 1024;
const ATTACHMENT_TEXT_MIMES: [&str; 9] = [
    "text/plain", "text/markdown", "text/csv",
    "application/json", "text/html",
    "application/yaml", "text/yaml", "application/x-yaml", "text/x-yaml",
];

fn validate_attachment_size(mime: &str, size: u64) -> Result<(), String> {
    let cap = if ATTACHMENT_TEXT_MIMES.contains(&mime) {
        ATTACHMENT_MAX_TEXT_BYTES
    } else {
        ATTACHMENT_MAX_FILE_BYTES
    };
    if size > cap {
        return Err(format!("file is too large ({} MB max)", cap / (1024 * 1024)));
    }
    Ok(())
}

// Remote daemon can't read local paths — upload bytes, return the daemon-side path.
#[tauri::command]
async fn attachment_stage(
    profile: String,
    path: String,
    mime: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    use base64::Engine;
    if mime.trim().is_empty() {
        return Err("unsupported attachment type".to_string());
    }
    let p = std::path::Path::new(&path);
    let name = p
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .ok_or_else(|| format!("invalid path: {path}"))?;
    let size = std::fs::metadata(p)
        .map_err(|e| format!("read {path}: {e}"))?
        .len();
    validate_attachment_size(&mime, size).map_err(|e| format!("{name}: {e}"))?;
    let bytes = std::fs::read(p).map_err(|e| format!("read {path}: {e}"))?;
    let b64 = base64::engine::general_purpose::STANDARD.encode(&bytes);
    let res = tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({
            "profile": profile,
            "name": name,
            "mime": mime,
            "data_base64": b64,
        });
        match connection_id {
            Some(cid) => host_client::call_for_fetch(&cid, "host.attachments.stage", params),
            None => host_client::call_fetch("host.attachments.stage", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    res.get("attachment")
        .cloned()
        .ok_or_else(|| "stage: response missing attachment".to_string())
}

// Produced attachments live on the daemon (possibly remote) — fetch the bytes
// over the host RPC, then let the user save them locally via a native dialog.
// Works for local and remote connections and for any served mime.
#[tauri::command]
async fn download_attachment(
    app: tauri::AppHandle, profile: String, path: String, connection_id: Option<String>,
) -> Result<Option<String>, String> {
    use base64::Engine;
    let res = tauri::async_runtime::spawn_blocking(move || {
        let params = serde_json::json!({"profile": profile, "path": path});
        match connection_id.as_deref() {
            Some(cid) => host_client::call_for_fetch(cid, "host.attachments.fetch", params),
            None => host_client::call_fetch("host.attachments.fetch", params),
        }
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    let name = res
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or("download")
        .to_string();
    let b64 = res
        .get("data_base64")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "fetch: response missing data".to_string())?;
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(b64)
        .map_err(|e| format!("decode: {e}"))?;
    let dest = tauri::async_runtime::spawn_blocking(move || {
        app.dialog().file().set_file_name(name).blocking_save_file()
    })
    .await
    .map_err(|e| format!("join: {e}"))?;
    let Some(dest) = dest.and_then(|f| f.into_path().ok()) else {
        return Ok(None); // user cancelled
    };
    std::fs::write(&dest, &bytes).map_err(|e| format!("write: {e}"))?;
    Ok(Some(dest.to_string_lossy().into_owned()))
}

// Linux has no portable "select file" — open the containing directory instead.
fn reveal_command(os: &str, path: &str) -> (&'static str, Vec<String>) {
    match os {
        "macos" => ("open", vec!["-R".into(), path.into()]),
        "windows" => ("explorer", vec![format!("/select,{path}")]),
        _ => {
            let dir = std::path::Path::new(path)
                .parent()
                .map(|p| p.to_string_lossy().into_owned())
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| path.into());
            ("xdg-open", vec![dir])
        }
    }
}

#[tauri::command]
fn reveal_in_finder(path: String) -> Result<(), String> {
    let os = if cfg!(target_os = "macos") {
        "macos"
    } else if cfg!(target_os = "windows") {
        "windows"
    } else {
        "linux"
    };
    let (program, args) = reveal_command(os, &path);
    Command::new(program)
        .args(&args)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("reveal: {e}"))
}

// Save a copy via the native save dialog; copies the original so it isn't re-encoded.
#[tauri::command]
async fn save_file_as(
    app: tauri::AppHandle, path: String, roots: Option<Vec<String>>,
) -> Result<bool, String> {
    let src = std::path::Path::new(&path);
    if !src.is_file() {
        return Err(format!("not a file: {path}"));
    }
    if !path_within_allowed(&path, &roots.unwrap_or_default()) {
        return Err("refused: path outside the allowed roots".into());
    }
    let default_name = src
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_else(|| "download".into());
    let dest = tauri::async_runtime::spawn_blocking(move || {
        app.dialog().file().set_file_name(default_name).blocking_save_file()
    })
    .await
    .map_err(|e| format!("join: {e}"))?;
    let Some(dest) = dest.and_then(|f| f.into_path().ok()) else {
        return Ok(false); // user cancelled
    };
    std::fs::copy(&path, &dest).map_err(|e| format!("copy: {e}"))?;
    Ok(true)
}

// Returns the full {models, errors} envelope so the UI can show *which*
// Ollama failed and why instead of "Ollama silently has no models".
#[tauri::command]
async fn ollama_models(profile: String) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.providers.ollama_models",
            serde_json::json!({"profile": profile}),
        )
    })
    .await
    .map_err(|e| format!("join: {e}"))?
}

#[tauri::command]
async fn chat_cancel(
    profile: String,
    request_id: Option<String>,
    connection_id: Option<String>,
) -> Result<(), String> {
    let connection_id = connection_id.unwrap_or_else(host_client::active_connection_id);
    let chat_key = active_chat_key(&connection_id, &profile);
    let request_id = match request_id {
        Some(rid) if !rid.is_empty() => Some(rid),
        _ => active_chats().lock().unwrap().get(&chat_key).cloned(),
    };
    let Some(request_id) = request_id else {
        return Ok(());
    };
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call_for(
            &connection_id,
            "host.chat.cancel",
            serde_json::json!({"request_id": request_id}),
        )
    })
    .await
    .map_err(|e| format!("chat_cancel: {e}"))?
    .map(|_| ())
}

#[tauri::command]
fn chat_send_stream(
    app: AppHandle,
    profile: String,
    session_id: Option<String>,
    rewrite_from_turn: Option<usize>,
    text: String,
    model: Option<String>,
    request_id: Option<String>,
    attachments: Option<serde_json::Value>,
    connection_id: Option<String>,
) {
    let connection_id = connection_id.unwrap_or_else(host_client::active_connection_id);
    thread::spawn(move || {
        stream_chat(
            app,
            connection_id,
            profile,
            session_id,
            rewrite_from_turn,
            text,
            model,
            request_id,
            attachments,
        )
    });
}

fn stream_chat(
    app: AppHandle,
    connection_id: String,
    profile: String,
    session_id: Option<String>,
    rewrite_from_turn: Option<usize>,
    text: String,
    model: Option<String>,
    request_id_opt: Option<String>,
    attachments: Option<serde_json::Value>,
) {
    let chat_key = active_chat_key(&connection_id, &profile);
    let request_id = request_id_opt.unwrap_or_else(|| format!(
        "tauri-{}-{}",
        profile,
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_micros())
            .unwrap_or(0)
    ));
    active_chats()
        .lock()
        .unwrap()
        .insert(chat_key.clone(), request_id.clone());

    let mut params = serde_json::json!({
        "profile": profile,
        "text": text,
        "request_id": request_id,
    });
    if let Some(id) = session_id {
        params["session_id"] = serde_json::Value::String(id);
    }
    if let Some(turn) = rewrite_from_turn {
        params["rewrite_from_turn"] = serde_json::Value::Number(turn.into());
    }
    if let Some(m) = model {
        params["model"] = serde_json::Value::String(m);
    }
    if let Some(a) = attachments {
        if !a.is_null() {
            params["attachments"] = a;
        }
    }

    let mut got_error = false;
    let mut got_interrupted = false;
    let mut resolved_id = String::new();
    let mut final_reply = String::new();
    let app_for_frames = app.clone();
    let rid_for_frames = request_id.clone();

    let result = host_client::call_stream_for(&connection_id, "host.chat.send", params, |frame| {
        if let Some(err) = frame.get("error") {
            got_error = true;
            let _ = app_for_frames.emit(
                "chat-event",
                ChatEvent::Error {
                    request_id: rid_for_frames.clone(),
                    text: err
                        .get("message")
                        .and_then(|v| v.as_str())
                        .unwrap_or("internal error")
                        .to_string(),
                },
            );
            return;
        }
        match frame
            .get("event")
            .and_then(|v| v.as_str())
            .unwrap_or("")
        {
            "session_start" => {
                let sid = frame["session_id"].as_str().unwrap_or("").to_string();
                if !sid.is_empty() {
                    resolved_id = sid.clone();
                }
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::SessionStart {
                        request_id: rid_for_frames.clone(),
                        session_id: sid,
                    },
                );
            }
            "tool_start" => {
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::ToolStart {
                        request_id: rid_for_frames.clone(),
                        tool_id: frame["tool_id"].as_str().unwrap_or("").to_string(),
                        name: frame["name"].as_str().unwrap_or("").to_string(),
                        preview: frame["preview"]
                            .as_str()
                            .unwrap_or("")
                            .to_string(),
                        args: frame
                            .get("args")
                            .cloned()
                            .unwrap_or(serde_json::Value::Object(Default::default())),
                    },
                );
            }
            "tool_state" => {
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::ToolState {
                        request_id: rid_for_frames.clone(),
                        tool_id: frame["tool_id"].as_str().unwrap_or("").to_string(),
                        name: frame["name"].as_str().unwrap_or("").to_string(),
                        text: frame["text"].as_str().unwrap_or("").to_string(),
                        ok: frame["ok"].as_bool().unwrap_or(true),
                    },
                );
            }
            "tool_end" => {
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::ToolEnd {
                        request_id: rid_for_frames.clone(),
                        tool_id: frame["tool_id"].as_str().unwrap_or("").to_string(),
                        name: frame["name"].as_str().unwrap_or("").to_string(),
                        ok: frame["ok"].as_bool().unwrap_or(false),
                        output: frame["output"]
                            .as_str()
                            .unwrap_or("")
                            .to_string(),
                    },
                );
            }
            "reasoning_delta" => {
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::ReasoningDelta {
                        request_id: rid_for_frames.clone(),
                        text: frame["text"].as_str().unwrap_or("").to_string(),
                    },
                );
            }
            "assistant_delta" => {
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::AssistantDelta {
                        request_id: rid_for_frames.clone(),
                        text: frame["text"].as_str().unwrap_or("").to_string(),
                    },
                );
            }
            "error" => {
                got_error = true;
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::Error {
                        request_id: rid_for_frames.clone(),
                        text: frame["text"].as_str().unwrap_or("").to_string(),
                    },
                );
            }
            "interrupted" => {
                got_interrupted = true;
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::Interrupted {
                        request_id: rid_for_frames.clone(),
                    },
                );
            }
            "auto_compact" => {
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::AutoCompact {
                        request_id: rid_for_frames.clone(),
                        text: frame["text"].as_str().unwrap_or("").to_string(),
                        tokens_before: frame["tokens_before"].as_u64().unwrap_or(0),
                        tokens_after: frame["tokens_after"].as_u64().unwrap_or(0),
                    },
                );
            }
            "usage" => {
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::Usage {
                        request_id: rid_for_frames.clone(),
                        tokens_in: frame["tokens_in"].as_u64().unwrap_or(0),
                        tokens_out: frame["tokens_out"].as_u64().unwrap_or(0),
                        cached_in: frame["cached_in"].as_u64().unwrap_or(0),
                        context_tokens: frame["context_tokens"].as_u64().unwrap_or(0),
                        cost: frame["cost"].as_f64().unwrap_or(0.0),
                        model: frame["model"].as_str().unwrap_or("").to_string(),
                    },
                );
            }
            "reply" => {
                final_reply = frame["text"].as_str().unwrap_or("").to_string();
                if let Some(sid) = frame.get("session_id").and_then(|v| v.as_str()) {
                    resolved_id = sid.to_string();
                }
            }
            "done" => {
                if let Some(sid) = frame.get("session_id").and_then(|v| v.as_str()) {
                    resolved_id = sid.to_string();
                }
            }
            "heartbeat" => {
                // Forward so the React watchdog treats the daemon as alive even on long tool calls with no deltas.
                let _ = app_for_frames.emit(
                    "chat-event",
                    ChatEvent::Heartbeat {
                        request_id: rid_for_frames.clone(),
                    },
                );
            }
            _ => {}
        }
    });

    if let Err(e) = result {
        if !got_error && !got_interrupted {
            let _ = app.emit(
                "chat-event",
                ChatEvent::Error {
                    request_id: request_id.clone(),
                    text: e,
                },
            );
        }
    }

    {
        let mut map = active_chats().lock().unwrap();
        if map.get(&chat_key).map(|s| s.as_str()) == Some(&request_id) {
            map.remove(&chat_key);
        }
    }

    let _ = app.emit(
        "chat-event",
        ChatEvent::Reply {
            request_id: request_id.clone(),
            text: final_reply,
            session_id: resolved_id.clone(),
        },
    );
    if !got_error && !got_interrupted {
        notifications::dispatch_session_done(&app, &connection_id, &profile, &resolved_id);
    }
    let _ = app.emit(
        "chat-event",
        ChatEvent::Done {
            request_id,
            session_id: resolved_id,
        },
    );
}

#[tauri::command]
async fn chat_events_since(
    profile: String,
    session_id: String,
    after_seq: Option<u64>,
    limit: Option<u64>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    // Replay sidecar for the freeze case: when host.chat.send's stream socket dies mid-turn, the desktop polls this to backfill missed frames.
    off_main(move || {
        let mut params = serde_json::json!({
            "profile": profile,
            "session_id": session_id,
        });
        if let Some(s) = after_seq {
            params["after_seq"] = serde_json::Value::from(s);
        }
        if let Some(l) = limit {
            params["limit"] = serde_json::Value::from(l);
        }
        match connection_id {
            Some(cid) => host_client::call_for(&cid, "host.chat.events_since", params),
            None => host_client::call("host.chat.events_since", params),
        }
    })
    .await?
}

#[tauri::command]
async fn workgroup_transcript(
    profile: String,
    wg_id: String,
    after_seq: Option<u32>,
    limit: Option<u32>,
    tail: Option<bool>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    // Default: tail=true, limit=200 — first-paint must be bounded so a workgroup with 10k posts doesn't ship megabytes over Tailscale. Subsequent fetches pass after_seq for incremental delta.
    off_main(move || workgroup_transcript_blocking(
        profile,
        wg_id,
        after_seq,
        limit,
        tail,
        connection_id,
    )).await?
}

fn workgroup_transcript_blocking(
    profile: String,
    wg_id: String,
    after_seq: Option<u32>,
    limit: Option<u32>,
    tail: Option<bool>,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut params = serde_json::json!({ "profile": profile, "wg_id": wg_id });
    if let Some(s) = after_seq {
        params["after_seq"] = serde_json::json!(s);
    } else if tail.unwrap_or(true) {
        params["tail"] = serde_json::json!(true);
    }
    params["limit"] = serde_json::json!(limit.unwrap_or(200));
    let result = match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.workgroup.transcript", params),
        None => host_client::call("host.workgroup.transcript", params),
    }?;
    let posts = result
        .get("posts")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut out: Vec<DecryptedMessage> = Vec::with_capacity(posts.len());
    for post in posts {
        let seq = post.get("seq").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
        let from = post
            .get("from")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let from_pubkey = post
            .get("from_pubkey")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let body = post
            .get("body")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let at = post
            .get("at")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let cost = post
            .get("cost")
            .cloned()
            .unwrap_or_else(|| serde_json::json!({}));
        out.push(DecryptedMessage {
            seq,
            from,
            from_pubkey,
            body,
            at,
            cost,
        });
    }
    let next_seq = result.get("next_seq").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
    Ok(serde_json::json!({
        "posts": out,
        "next_seq": next_seq,
    }))
}

#[tauri::command]
async fn workgroup_tasks(
    profile: String,
    wg_id: String,
    connection_id: Option<String>,
) -> Result<serde_json::Value, String> {
    let params = serde_json::json!({ "profile": profile, "wg_id": wg_id });
    off_main(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.workgroup.tasks", params),
        None => host_client::call("host.workgroup.tasks", params),
    })
    .await?
}

#[tauri::command]
async fn workgroup_post(
    profile: String,
    wg_id: String,
    text: String,
    connection_id: Option<String>,
) -> Result<String, String> {
    let params = serde_json::json!({ "profile": profile, "wg_id": wg_id, "text": text });
    let result = tauri::async_runtime::spawn_blocking(move || match connection_id.as_deref() {
        Some(cid) => host_client::call_for(cid, "host.workgroup.post", params),
        None => host_client::call("host.workgroup.post", params),
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(result
        .get("seq")
        .map(|v| v.to_string())
        .unwrap_or_default())
}

#[tauri::command]
async fn tts_synthesize(voice: String, text: String) -> Result<String, String> {
    use base64::Engine;
    let audio = tts::synthesize_cached(&voice, &text).await?;
    Ok(base64::engine::general_purpose::STANDARD.encode(audio.as_ref()))
}

#[tauri::command]
async fn voice_script(profile: String, text: String) -> Result<String, String> {
    off_main(move || {
        let res = host_client::call(
            "host.voice.script",
            serde_json::json!({"profile": profile, "text": text}),
        )?;
        Ok(res
            .get("script")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .to_string())
    })
    .await?
}

#[tauri::command]
fn tray_announce_update(app: AppHandle, available: bool, version: Option<String>) {
    tray::announce_update(&app, available, version.as_deref());
}

#[tauri::command]
fn tray_announce_notifications(app: AppHandle, unread: u64) {
    tray::announce_notifications(&app, unread);
}

fn subscribe_daemon_events(app: AppHandle) {
    use std::collections::HashMap;
    use std::sync::{Arc, Mutex};

    use crate::event_dispatch::{classify_frame, SubscribeAction, SubscribeState};

    // One state object per (daemon connection). Keeps last_seq + the dedupe window. Survives loop iterations so reconnects retain the cursor.
    let states: Arc<Mutex<HashMap<String, SubscribeState>>> =
        Arc::new(Mutex::new(HashMap::new()));

    // This loop doubles as the recovery detector for the active daemon — back off while it stays down (2,4,8,10s capped) so an offline remote isn't hammered, reset as soon as a stream lives.
    let mut consecutive_failures: u32 = 0;
    loop {
        let starting_id = host_client::active_connection_id();
        let Some(sub_key) = host_client::active_subscription_key() else {
            host_client::probe_active();
            std::thread::sleep(std::time::Duration::from_secs(2));
            continue;
        };
        let app_for_frames = app.clone();
        let id_for_payload = starting_id.clone();
        let states_for_loop = Arc::clone(&states);
        let starting_id_for_match = starting_id.clone();
        let key_for_loop = sub_key.clone();

        let stream_result = host_client::call_stream_until(
            "host.events.subscribe",
            serde_json::json!({}),
            move |frame| {
                if host_client::active_connection_id() != starting_id_for_match {
                    return false;
                }
                let mut guard = states_for_loop
                    .lock()
                    .unwrap_or_else(|e| e.into_inner());
                let state = guard
                    .entry(key_for_loop.clone())
                    .or_insert_with(|| SubscribeState::new(1024));
                let action = classify_frame(state, &frame);
                drop(guard);

                match action {
                    SubscribeAction::BackfillFrom(prev) => {
                        if let Ok(value) = host_client::call(
                            "host.events.history",
                            serde_json::json!({ "after_seq": prev, "limit": 200 }),
                        ) {
                            if let Some(events) =
                                value.get("events").and_then(|v| v.as_array())
                            {
                                for ev in events {
                                    let mut g = states_for_loop
                                        .lock()
                                        .unwrap_or_else(|e| e.into_inner());
                                    let s = g.entry(key_for_loop.clone())
                                        .or_insert_with(|| SubscribeState::new(1024));
                                    if let Some(seq) =
                                        ev.get("seq").and_then(|v| v.as_u64())
                                    {
                                        if !s.mark_seen(seq) {
                                            continue;
                                        }
                                        s.bump_seq(seq);
                                    }
                                    drop(g);
                                    notifications::dispatch_daemon_frame(
                                        &app_for_frames,
                                        &id_for_payload,
                                        true,
                                        ev,
                                    );
                                    let _ = app_for_frames.emit(
                                        "daemon-event",
                                        serde_json::json!({
                                            "connection_id": id_for_payload,
                                            "frame": ev,
                                            "replay": true,
                                        }),
                                    );
                                }
                            }
                            if let Some(next) =
                                value.get("next_seq").and_then(|v| v.as_u64())
                            {
                                let mut g = states_for_loop
                                    .lock()
                                    .unwrap_or_else(|e| e.into_inner());
                                g.entry(key_for_loop.clone())
                                    .or_insert_with(|| SubscribeState::new(1024))
                                    .bump_seq(next);
                            }
                        }
                    }
                    SubscribeAction::AnchorAt(anchor) => {
                        if anchor > 0 {
                            let mut g = states_for_loop
                                .lock()
                                .unwrap_or_else(|e| e.into_inner());
                            g.entry(key_for_loop.clone())
                                .or_insert_with(|| SubscribeState::new(1024))
                                .bump_seq(anchor);
                        }
                    }
                    SubscribeAction::Deliver { .. } => {
                        notifications::dispatch_daemon_frame(&app_for_frames, &id_for_payload, true, &frame);
                        let _ = app_for_frames.emit(
                            "daemon-event",
                            serde_json::json!({
                                "connection_id": id_for_payload,
                                "frame": frame,
                            }),
                        );
                    }
                    SubscribeAction::DuplicateSeq | SubscribeAction::Ignore => {}
                }
                true
            },
        );
        let sleep_secs = match &stream_result {
            Ok(()) => {
                consecutive_failures = 0;
                2
            }
            Err(_) => {
                consecutive_failures = consecutive_failures.saturating_add(1);
                (2u64 << consecutive_failures.min(3)).min(10)
            }
        };
        std::thread::sleep(std::time::Duration::from_secs(sleep_secs));
    }
}

const INACTIVE_POLL_SECS: u64 = 25;

// The active connection notifies via its instant stream; this polls every OTHER connection so background daemons still raise native notifications.
fn poll_inactive_connections(app: AppHandle) {
    use std::collections::{HashMap, HashSet};

    use crate::event_dispatch::{classify_poll, NOTIFIABLE_KINDS};

    let mut cursors: HashMap<String, u64> = HashMap::new();
    loop {
        std::thread::sleep(std::time::Duration::from_secs(INACTIVE_POLL_SECS));
        let state = host_client::load_connections();
        let active = host_client::active_connection_id();
        let known: HashSet<String> =
            state.connections.iter().map(|c| c.id().to_string()).collect();
        cursors.retain(|id, _| known.contains(id));
        for conn in &state.connections {
            let id = conn.id().to_string();
            if id == active {
                // Drop so it re-anchors (no replay) the moment it stops being active.
                cursors.remove(&id);
                continue;
            }
            // Members have no inbox — the daemon filters their events to empty, so polling is pure wasted traffic.
            if host_client::effective_role(conn).as_deref() == Some("member") {
                cursors.remove(&id);
                continue;
            }
            let cursor = cursors.get(&id).copied();
            let params = serde_json::json!({
                "after_seq": cursor.unwrap_or(0),
                "limit": 50,
                "kinds": NOTIFIABLE_KINDS,
            });
            let resp = match host_client::call_for(&id, "host.events.history", params) {
                Ok(v) => v,
                Err(_) => continue,
            };
            let events: Vec<serde_json::Value> = resp
                .get("events")
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default();
            let next_seq = resp.get("next_seq").and_then(|v| v.as_u64());
            let outcome = classify_poll(cursor, &events, next_seq);
            for frame in &outcome.to_notify {
                notifications::dispatch_daemon_frame(&app, &id, false, frame);
                // background flag: useAllOutputs refreshes on this even though the poller carries agent.message/etc., not output.created.
                let _ = app.emit(
                    "daemon-event",
                    serde_json::json!({
                        "connection_id": id.clone(),
                        "frame": frame.clone(),
                        "background": true,
                    }),
                );
            }
            cursors.insert(id, outcome.next_cursor);
        }
    }
}

#[tauri::command]
fn set_active_view(kind: Option<String>, id: Option<String>) {
    notifications::set_active_view(kind, id);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
fn install_app_menu(app: &AppHandle) -> tauri::Result<()> {
    // NSAboutPanel renders name, version, copyright, credits and icon — credits is plain text, no markup, left-aligned by macOS. Short, equal-width lines look balanced.
    let credits = concat!(
        "Local-first agent that grows with you.\n",
        "Each profile owns its memory, keys, model\n",
        "and trust boundary; ALP links them across\n",
        "machines without a registry or central cloud.\n",
        "\n",
        "github.com/satoshi-ltd/alpi\n",
        "BUSL-1.1",
    );
    let icon = tauri::image::Image::from_bytes(include_bytes!("../icons/128x128@2x.png")).ok();
    let mut about = AboutMetadataBuilder::new()
        .name(Some("Alpi"))
        .version(Some(env!("CARGO_PKG_VERSION")))
        .authors(Some(vec!["Satoshi Ltd.".to_string()]))
        .copyright(Some("© 2026 Satoshi Ltd."))
        .website(Some("https://alpi.satoshi.ltd"))
        .website_label(Some("alpi.satoshi.ltd"))
        .license(Some("BUSL-1.1"))
        .credits(Some(credits.to_string()));
    if let Some(icon) = icon {
        about = about.icon(Some(icon));
    }
    let about = about.build();

    let about_item =
        PredefinedMenuItem::about(app, Some("About Alpi"), Some(about))?;
    let settings_item =
        MenuItem::with_id(app, "menu:settings", "Settings…", true, Some("CmdOrCtrl+,"))?;
    let sep_a = PredefinedMenuItem::separator(app)?;
    let hide = PredefinedMenuItem::hide(app, None)?;
    let hide_others = PredefinedMenuItem::hide_others(app, None)?;
    let show_all = PredefinedMenuItem::show_all(app, None)?;
    let sep_b = PredefinedMenuItem::separator(app)?;
    let services = Submenu::with_id(app, "menu:services", "Services", true)?;
    let sep_c = PredefinedMenuItem::separator(app)?;
    let quit = PredefinedMenuItem::quit(app, Some("Quit Alpi"))?;

    let app_submenu = Submenu::with_items(
        app,
        "Alpi",
        true,
        &[
            &about_item,
            &sep_a,
            &settings_item,
            &sep_b,
            &services,
            &sep_c,
            &hide,
            &hide_others,
            &show_all,
            &sep_c,
            &quit,
        ],
    )?;

    let undo = PredefinedMenuItem::undo(app, None)?;
    let redo = PredefinedMenuItem::redo(app, None)?;
    let edit_sep = PredefinedMenuItem::separator(app)?;
    let cut = PredefinedMenuItem::cut(app, None)?;
    let copy = PredefinedMenuItem::copy(app, None)?;
    let paste = PredefinedMenuItem::paste(app, None)?;
    let select_all = PredefinedMenuItem::select_all(app, None)?;
    let edit_submenu = Submenu::with_items(
        app,
        "Edit",
        true,
        &[&undo, &redo, &edit_sep, &cut, &copy, &paste, &select_all],
    )?;

    let menu = Menu::with_items(app, &[&app_submenu, &edit_submenu])?;
    app.set_menu(menu)?;
    app.on_menu_event(|app, event| {
        if event.id.as_ref() == "menu:settings" {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.unminimize();
                let _ = window.set_focus();
                let _ = window.emit("nav", "settings");
            }
        }
    });
    Ok(())
}

pub fn run() {
    let toggle_shortcut = Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::KeyA);

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.show();
                let _ = w.unminimize();
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, shortcut, event| {
                    // Bring-to-front only — a toggle would hide the window when it's visible but unfocused, the exact moment the user is summoning it.
                    if event.state() == ShortcutState::Pressed && shortcut == &toggle_shortcut {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.unminimize();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(),
        )
        .setup(move |app| {
            install_app_menu(app.handle())?;
            tray::install(app)?;
            if let Err(e) = app.global_shortcut().register(toggle_shortcut) {
                eprintln!("global shortcut register failed: {e}");
            }
            if let Err(e) = watcher::install(app.handle()) {
                eprintln!("watcher install failed: {e}");
            }
            let app_handle = app.handle().clone();
            let app_for_status = app_handle.clone();
            host_client::on_status_change(move |id, status, error| {
                let _ = app_for_status.emit(
                    "connection-status",
                    serde_json::json!({
                        "id": id,
                        "status": match status {
                            host_client::ConnectionStatus::Online => "online",
                            host_client::ConnectionStatus::Probing => "probing",
                            host_client::ConnectionStatus::Offline => "offline",
                            host_client::ConnectionStatus::Disabled => "disabled",
                            host_client::ConnectionStatus::AuthFailed => "auth-failed",
                            host_client::ConnectionStatus::Unknown => "unknown",
                        },
                        "error": error,
                        "alpi_version": host_client::version_for(id),
                        "update_available": host_client::update_available_for(id),
                        "role": host_client::role_for(id),
                    }),
                );
                if matches!(status, host_client::ConnectionStatus::Offline)
                    && id == host_client::active_connection_id().as_str()
                {
                    notifications::dispatch_daemon_disconnect(&app_for_status, id);
                }
            });
            spawn_background("probe-active-startup", host_client::probe_active);
            // Deferred, bounded host.version backfill fills persisted-role gaps (legacy connections.json, never-probed remotes) so inactive-connection fetch/poll gates are right without waiting for the connection sheet.
            spawn_background("backfill-roles-startup", || {
                std::thread::sleep(std::time::Duration::from_secs(3));
                host_client::backfill_missing_roles();
            });
            spawn_background("probe-active-loop", || loop {
                std::thread::sleep(std::time::Duration::from_secs(30));
                host_client::probe_active();
            });
            let app_for_poll = app_handle.clone();
            spawn_background("inactive-poll", move || poll_inactive_connections(app_for_poll));
            spawn_background("daemon-events", move || subscribe_daemon_events(app_handle));
            Ok(())
        })
        .on_window_event(|window, event| {
            // Close-to-tray keeps the process (and with it ⌘⇧A + tray notifications) alive — destroying the only window would exit the app.
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .invoke_handler(tauri::generate_handler![
            profiles,
            profile_summaries,
            profile_detail,
            settings_profile_snapshot,
            usage_daily,
            workgroup_usage_daily,
            profile_tools,
            profile_skills,
            profile_skill_read,
            profile_skill_file,
            profile_memory,
            memory_usage,
            memory_read,
            memory_write,
            host_connections,
            host_connection_set_active,
            host_connection_forget,
            host_connection_add_remote,
            host_connections_probe_active,
            host_connections_probe_all,
            host_connection_probe,
            sessions,
            runs_list,
            run_read,
            run_cancel,
            session_detail,
            sessions_delete,
            workgroups,
            workgroup_transcript,
            workgroup_post,
            tts_synthesize,
            voice_script,
            read_file,
            chat_send_stream,
            chat_cancel,
            chat_events_since,
            ollama_models,
            set_config_field,
            unset_config_field,
            draft_identity,
            port_available,
            service_action,
            reveal_in_finder,
            save_file_as,
            email_status,
            pick_folder,
            pick_files,
            attachment_meta,
            attachment_thumb,
            save_text_file,
            attachment_stage,
            download_attachment,
            probe_peers,
            peer_add,
            peer_remove,
            peers_pending_list,
            peers_pending_accept,
            peers_pending_discard,
            schedules,
            schedule_remove,
            schedule_set_paused,
            schedule_fire,
            daemon_restart,
            daemon_update,
            outputs_list,
            outputs_read,
            outputs_mark_read,
            outputs_mark_all_read,
            outputs_delete,
            approval_respond,
            approval_pending,
            clarification_respond,
            clarification_pending,
            profile_create,
            profile_delete,
            provider_set_key,
            provider_unset_key,
            provider_add_ollama,
            provider_remove_ollama,
            provider_add_openrouter_model,
            provider_remove_openrouter_model,
            sandbox_set,
            sandbox_network,
            voice_set_voice,
            voice_set_auto_read,
            email_config,
            email_gmail_authorize,
            email_gmail_paste,
            email_add,
            email_remove,
            mcp_add,
            mcp_remove,
            profile_mcp_tools,
            resolve_ctx_window,
            probe_email,
            devices_list,
            devices_generate,
            devices_set_profiles,
            devices_promote,
            devices_demote,
            devices_revoke,
            devices_rename,
            connections_summary,
            connections_create,
            connections_add_device,
            connections_pairing_status,
            connections_cancel_pairing,
            connections_update,
            connections_set_status,
            connections_delete,
            connections_revoke_device,
            audit_list,
            network_status,
            network_set_advertised,
            network_restart_host_server,
            profile_storage,
            cleanup_plan,
            cleanup_apply,
            workgroup_members,
            workgroup_action,
            workgroup_update,
            workgroup_tasks,
            workgroup_create,
            workgroup_pick_recipe,
            workgroup_saved_recipes,
            workgroup_launch_recipe,
            workgroup_add_member,
            tray_announce_update,
            tray_announce_notifications,
            set_active_view
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod chat_event_tests {
    use super::ChatEvent;

    #[test]
    fn usage_event_keeps_context_tokens_distinct_from_side_call_usage() {
        let event = ChatEvent::Usage {
            request_id: "req-1".to_string(),
            tokens_in: 42_000,
            tokens_out: 120,
            cached_in: 10_000,
            context_tokens: 42_000,
            cost: 0.0031,
            model: "openrouter/z-ai/glm-5.3-flash".to_string(),
        };
        let value = serde_json::to_value(event).unwrap();
        assert_eq!(value["kind"], "usage");
        assert_eq!(value["context_tokens"], 42_000);
        assert_eq!(value["model"], "openrouter/z-ai/glm-5.3-flash");
    }
}

#[cfg(test)]
mod path_allow_tests {
    use super::path_within_allowed;

    #[test]
    fn allows_temp_refuses_outside_and_missing() {
        let f = std::env::temp_dir().join("alpi_pwa_test.txt");
        std::fs::write(&f, b"x").unwrap();
        assert!(path_within_allowed(f.to_str().unwrap(), &[]));
        let _ = std::fs::remove_file(&f);
        assert!(!path_within_allowed("/tmp/alpi-does-not-exist-zzz.png", &[]));
        // Outside default roots → refused; a passed (workspace) root extends the allowlist.
        assert!(!path_within_allowed("/etc/hosts", &[]));
        assert!(path_within_allowed("/etc/hosts", &["/etc".to_string()]));
    }
}

#[cfg(test)]
mod reveal_tests {
    use super::reveal_command;

    #[test]
    fn macos_selects_the_file_with_spaces() {
        assert_eq!(
            reveal_command("macos", "/Users/a/My File.png"),
            ("open", vec!["-R".to_string(), "/Users/a/My File.png".to_string()]),
        );
    }

    #[test]
    fn windows_selects_the_file_with_spaces() {
        assert_eq!(
            reveal_command("windows", "C:\\Users\\a\\My File.png"),
            ("explorer", vec!["/select,C:\\Users\\a\\My File.png".to_string()]),
        );
    }

    #[test]
    fn linux_opens_the_containing_directory() {
        assert_eq!(
            reveal_command("linux", "/home/a/My File.png"),
            ("xdg-open", vec!["/home/a".to_string()]),
        );
    }

    #[test]
    fn linux_falls_back_to_path_when_no_parent() {
        assert_eq!(reveal_command("linux", "/"), ("xdg-open", vec!["/".to_string()]));
        assert_eq!(reveal_command("linux", "file.png"), ("xdg-open", vec!["file.png".to_string()]));
    }
}

#[cfg(test)]
mod daemon_start_tests {
    use super::{daemon_start_argv, Supervisor};

    #[test]
    fn picks_supervisor_specific_command() {
        // installed supervisor → ask it (no competing foreground daemon); none → spawn directly.
        assert_eq!(
            daemon_start_argv(Supervisor::Launchd, 501),
            ["launchctl", "kickstart", "gui/501/com.alpi.daemon"],
        );
        assert_eq!(
            daemon_start_argv(Supervisor::Systemd, 1000),
            ["systemctl", "--user", "start", "alpi-daemon.service"],
        );
        assert_eq!(daemon_start_argv(Supervisor::None, 0), ["alpi", "daemon", "start"]);
    }
}

#[cfg(test)]
mod oauth_callback_tests {
    use super::{parse_oauth_callback, parse_oauth_callback_input, percent_decode};

    #[test]
    fn parse_extracts_code_state_error() {
        let (c, s, e) = parse_oauth_callback("/?code=abc&state=xyz");
        assert_eq!(c, "abc");
        assert_eq!(s, "xyz");
        assert_eq!(e, "");

        let (c, s, e) = parse_oauth_callback("/?error=access_denied&state=zzz");
        assert_eq!(c, "");
        assert_eq!(s, "zzz");
        assert_eq!(e, "access_denied");
    }

    #[test]
    fn parse_ignores_unknown_keys_and_handles_no_query() {
        let (c, s, e) = parse_oauth_callback("/?foo=bar&code=ok&baz=qux");
        assert_eq!(c, "ok");
        assert_eq!(s, "");
        assert_eq!(e, "");

        let (c, s, e) = parse_oauth_callback("/");
        assert!(c.is_empty() && s.is_empty() && e.is_empty());
    }

    #[test]
    fn parse_decodes_percent_and_plus() {
        // Google does not actually percent-encode the code, but defend
        // anyway — easier than reasoning about provider quirks.
        let (c, _, _) = parse_oauth_callback("/?code=hello%20world");
        assert_eq!(c, "hello world");
        let (c, _, _) = parse_oauth_callback("/?code=a+b%2Bc");
        assert_eq!(c, "a b+c");
    }

    #[test]
    fn percent_decode_handles_truncated_escape() {
        // Stray % at end-of-input must not panic.
        assert_eq!(percent_decode("abc%"), "abc%");
        assert_eq!(percent_decode("abc%2"), "abc%2");
        assert_eq!(percent_decode("abc%2Q"), "abc%2Q"); // not hex
    }

    #[test]
    fn input_accepts_full_url() {
        let (c, s, e) =
            parse_oauth_callback_input("http://127.0.0.1:55989/?code=abc&state=xyz");
        assert_eq!(c, "abc");
        assert_eq!(s, "xyz");
        assert!(e.is_empty());
    }

    #[test]
    fn input_accepts_query_only() {
        let (c, s, _) = parse_oauth_callback_input("/?code=abc&state=xyz");
        assert_eq!(c, "abc");
        assert_eq!(s, "xyz");
    }

    #[test]
    fn input_trims_whitespace() {
        let (c, _, _) =
            parse_oauth_callback_input("  http://127.0.0.1:1/?code=trimmed&state=x  \n");
        assert_eq!(c, "trimmed");
    }

    #[test]
    fn input_tolerates_https_scheme() {
        // Google sometimes appends to a URL the user could mistakenly grab
        // from a redirector — the parser still works after the first '/'.
        let (c, _, _) = parse_oauth_callback_input("https://anything/?code=ok&state=s");
        assert_eq!(c, "ok");
    }

    #[test]
    fn input_returns_empty_when_no_query() {
        let (c, s, e) = parse_oauth_callback_input("http://127.0.0.1:1/");
        assert!(c.is_empty() && s.is_empty() && e.is_empty());
    }
}

#[cfg(test)]
mod attachment_size_tests {
    use super::*;

    #[test]
    fn general_files_pass_up_to_20_mib() {
        assert!(validate_attachment_size("application/pdf", ATTACHMENT_MAX_FILE_BYTES).is_ok());
        assert!(validate_attachment_size("image/png", 5 * 1024 * 1024).is_ok());
    }

    #[test]
    fn general_files_over_20_mib_are_rejected() {
        let err = validate_attachment_size("application/pdf", ATTACHMENT_MAX_FILE_BYTES + 1)
            .unwrap_err();
        assert!(err.contains("20 MB max"), "{err}");
    }

    #[test]
    fn text_files_cap_at_2_mib() {
        assert!(validate_attachment_size("text/plain", ATTACHMENT_MAX_TEXT_BYTES).is_ok());
        let err = validate_attachment_size("text/plain", ATTACHMENT_MAX_TEXT_BYTES + 1)
            .unwrap_err();
        assert!(err.contains("2 MB max"), "{err}");
    }

    #[test]
    fn every_text_mime_gets_the_text_cap() {
        for mime in ATTACHMENT_TEXT_MIMES {
            assert!(
                validate_attachment_size(mime, ATTACHMENT_MAX_TEXT_BYTES + 1).is_err(),
                "{mime} should use the text cap",
            );
        }
    }
}
