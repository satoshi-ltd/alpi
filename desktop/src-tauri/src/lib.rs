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

fn active_chats() -> &'static Mutex<HashMap<String, String>> {
    static SLOT: OnceLock<Mutex<HashMap<String, String>>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(HashMap::new()))
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
fn profiles() -> serde_json::Value {
    host_array_value("host.profiles.list", serde_json::json!({}), "profiles")
}

#[tauri::command]
fn profile_tools(profile: String) -> serde_json::Value {
    host_array_value(
        "host.tools.list",
        serde_json::json!({ "profile": profile }),
        "tools",
    )
}

#[tauri::command]
fn profile_skills(profile: String) -> serde_json::Value {
    host_array_value(
        "host.skills.list",
        serde_json::json!({ "profile": profile }),
        "skills",
    )
}

#[tauri::command]
fn profile_skill_read(
    profile: String,
    name: String,
    category: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut params = serde_json::json!({ "profile": profile, "name": name });
    if let Some(cat) = category {
        params["category"] = serde_json::Value::String(cat);
    }
    host_client::call("host.skill.read", params)
        .map(|v| v.get("skill").cloned().unwrap_or(serde_json::Value::Null))
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn profile_detail(profile: String) -> Result<serde_json::Value, String> {
    host_client::call(
        "host.profile.detail",
        serde_json::json!({ "profile": profile }),
    )
    .map_err(|e| e.to_string())
}

#[tauri::command]
fn profile_memory(profile: String) -> Result<serde_json::Value, String> {
    let mut out = serde_json::Map::new();
    for name in ["USER.md", "MEMORY.md", "AGENT.md"] {
        let rel = format!("memories/{name}");
        let text = host_client::call(
            "host.profile.read_file",
            serde_json::json!({ "profile": profile, "rel_path": rel }),
        )
        .ok()
        .and_then(|v| v.get("text").and_then(|t| t.as_str()).map(String::from))
        .unwrap_or_default();
        out.insert(name.to_string(), serde_json::Value::String(text));
    }
    Ok(serde_json::Value::Object(out))
}

#[tauri::command]
fn profile_summaries() -> serde_json::Value {
    host_array_value("host.profile.summaries", serde_json::json!({}), "profiles")
}

#[tauri::command]
fn host_connections() -> serde_json::Value {
    host_client::connections_for_ui()
}

#[tauri::command]
fn host_connection_set_active(id: String) -> Result<(), String> {
    host_client::set_active_connection(id)
}

#[tauri::command]
fn host_connection_forget(id: String) -> Result<(), String> {
    host_client::forget_connection(id)
}

#[tauri::command]
fn host_connection_add_remote(
    name: String,
    host: String,
    port: u16,
    token: String,
) -> Result<String, String> {
    host_client::add_remote_connection(name, host, port, token)
}

fn spawn_background(name: &str, f: impl FnOnce() + Send + 'static) {
    if let Err(e) = thread::Builder::new().name(name.to_string()).spawn(f) {
        eprintln!("background task {name} not started: {e}");
    }
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
            host_client::ConnectionStatus::AuthFailed => "auth-failed",
            host_client::ConnectionStatus::Unknown => "unknown",
        }
        .to_string()
    })
    .await
    .unwrap_or_else(|_| "unknown".to_string())
}

#[tauri::command]
fn sessions(profile: Option<String>, limit: Option<usize>) -> Vec<SessionEntry> {
    match profile {
        Some(p) => sessions_via_alp(&p, limit),
        None => host_profile_names()
            .into_iter()
            .flat_map(|p| sessions_via_alp(&p, limit))
            .collect(),
    }
}

fn host_profile_names() -> Vec<String> {
    let value = host_array_value("host.profiles.list", serde_json::json!({}), "profiles");
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

fn sessions_via_alp(profile: &str, limit: Option<usize>) -> Vec<SessionEntry> {
    let mut params = serde_json::json!({"profile": profile});
    if let Some(limit) = limit {
        params["limit"] = serde_json::json!(limit);
    }
    let result = match host_client::call(
        "host.sessions.list",
        params,
    ) {
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
        out.push(SessionEntry {
            id,
            profile: profile.to_string(),
            mtime,
            started_at,
            updated_at,
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
fn session_detail(profile: String, id: String) -> Result<serde_json::Value, String> {
    let result = host_client::call(
        "host.session.read",
        serde_json::json!({"profile": profile, "id": id}),
    )?;
    Ok(result.get("session").cloned().unwrap_or(serde_json::Value::Null))
}

#[tauri::command]
fn workgroups(profile: Option<String>) -> serde_json::Value {
    let params = match profile {
        Some(p) => serde_json::json!({"profile": p}),
        None => serde_json::json!({}),
    };
    host_array_value("host.workgroups.list", params, "workgroups")
}

#[tauri::command]
fn read_file(profile: Option<String>, rel_path: String) -> Result<String, String> {
    let mut params = serde_json::json!({"rel_path": rel_path});
    if let Some(p) = profile {
        params["profile"] = serde_json::Value::String(p);
    }
    let result = host_client::call("host.profile.read_file", params)?;
    Ok(result
        .get("text")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string())
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

// Local subprocess: daemon may not be running yet (start/install case).
#[tauri::command]
async fn service_action(profile: String, action: String) -> Result<String, String> {
    if !matches!(
        action.as_str(),
        "start" | "stop" | "restart" | "install" | "uninstall"
    ) {
        return Err(format!("invalid action: {action}"));
    }
    if action == "start" {
        return tauri::async_runtime::spawn_blocking(move || {
            Command::new("alpi")
                .args(["-p", &profile, "service", "start"])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .map_err(|e| format!("spawn `alpi`: {e}"))?;
            if let Some(home) = crate::home::resolve_home(Some(&profile)) {
                let pid_path = home.join("service.pid");
                for _ in 0..60 {
                    if pid_path.exists() {
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(50));
                }
            }
            Ok("started".into())
        })
        .await
        .map_err(|e| format!("join: {e}"))?;
    }
    let action_for_msg = action.clone();
    let profile_for_wait = profile.clone();
    let action_for_wait = action.clone();
    let out = tauri::async_runtime::spawn_blocking(move || {
        Command::new("alpi")
            .args(["-p", &profile, "service", &action])
            .output()
    })
    .await
    .map_err(|e| format!("join: {e}"))?
    .map_err(|e| format!("spawn `alpi`: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "service {} failed: {}",
            action_for_msg,
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    if action_for_wait == "restart" || action_for_wait == "install" {
        tauri::async_runtime::spawn_blocking(move || {
            if let Some(home) = crate::home::resolve_home(Some(&profile_for_wait)) {
                let pid_path = home.join("service.pid");
                for _ in 0..60 {
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
fn gateway_status(profile: String) -> serde_json::Value {
    host_array_value(
        "host.gateway.status",
        serde_json::json!({"profile": profile}),
        "gateways",
    )
}

#[tauri::command]
fn devices_list() -> serde_json::Value {
    host_array_value("host.devices.list", serde_json::json!({}), "devices")
}

#[tauri::command]
async fn devices_generate(label: String) -> Result<serde_json::Value, String> {
    let value = tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.devices.generate",
            serde_json::json!({"label": label}),
        )
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(value)
}

#[tauri::command]
async fn devices_revoke(token_id: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.devices.revoke",
            serde_json::json!({"token_id": token_id}),
        )
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
}

#[tauri::command]
async fn devices_rename(token_id: String, label: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.devices.rename",
            serde_json::json!({"token_id": token_id, "label": label}),
        )
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
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
    host: String,
    device_name: String,
) -> Result<serde_json::Value, String> {
    let value = tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.network.set_advertised",
            serde_json::json!({"host": host, "device_name": device_name}),
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
fn profile_storage(profile: String) -> serde_json::Value {
    host_array_value(
        "host.profile.storage",
        serde_json::json!({"profile": profile}),
        "storage",
    )
}

#[tauri::command]
fn workgroup_members(profile: String, wg_id: String) -> serde_json::Value {
    host_array_value(
        "host.workgroup.members",
        serde_json::json!({"profile": profile, "wg_id": wg_id}),
        "members",
    )
}

#[tauri::command]
async fn workgroup_create(
    profile: String,
    name: String,
    member_peer_ids: Vec<String>,
    budget_usd: Option<f64>,
    briefing: Option<String>,
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
        host_client::call("host.workgroup.create", params)
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
async fn workgroup_update(
    profile: String,
    wg_id: String,
    briefing: Option<String>,
    budget_usd: Option<f64>,
    clear_budget: Option<bool>,
) -> Result<(), String> {
    let mut params = serde_json::json!({ "profile": profile, "wg_id": wg_id });
    if let Some(b) = briefing {
        params["briefing"] = serde_json::Value::String(b);
    }
    if clear_budget.unwrap_or(false) {
        params["clear_budget"] = serde_json::json!(true);
    } else if let Some(b) = budget_usd {
        params["budget_usd"] = serde_json::json!(b);
    }
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call("host.workgroup.update", params)
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
) -> Result<(), String> {
    let params = serde_json::json!({ "profile": profile, "wg_id": wg_id, "member": member });
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call("host.workgroup.add_member", params)
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
    tauri::async_runtime::spawn_blocking(move || host_client::call(method, params))
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
async fn probe_gateways(
    profile: String,
    only: Option<Vec<String>>,
) -> Vec<GatewayProbe> {
    let names: Vec<String> = match only {
        Some(list) if !list.is_empty() => list,
        _ => vec!["telegram".into(), "imap".into(), "gmail".into(), "matrix".into()],
    };
    let mut handles = vec![];
    for name in names {
        let p = profile.clone();
        let n = name.clone();
        handles.push(tauri::async_runtime::spawn_blocking(move || {
            let result = host_client::call(
                "host.gateway.probe",
                serde_json::json!({ "profile": p, "name": n.clone() }),
            );
            let (status, reason) = match result {
                Ok(v) => (
                    v.get("status").and_then(|x| x.as_str()).unwrap_or("off").to_string(),
                    v.get("reason").and_then(|x| x.as_str()).map(|x| x.to_string()),
                ),
                Err(_) => ("off".to_string(), None),
            };
            GatewayProbe {
                name: n,
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
fn gateway_config(profile: String, name: String) -> std::collections::HashMap<String, String> {
    host_client::call(
        "host.gateway.config",
        serde_json::json!({"profile": profile, "name": name}),
    )
    .ok()
    .and_then(|v| v.get("config").cloned())
    .and_then(|v| serde_json::from_value(v).ok())
    .unwrap_or_default()
}

#[tauri::command]
async fn gateway_gmail_authorize(
    app: AppHandle,
    profile: String,
    client_id: String,
    client_secret: String,
    allowed_senders: String,
) -> Result<(), String> {
    let params = serde_json::json!({
        "profile": profile,
        "client_id": client_id,
        "client_secret": client_secret,
        "allowed_senders": allowed_senders,
    });
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call_stream("host.gateway.gmail_authorize", params, move |frame| {
            let _ = app.emit("gmail-auth-event", frame);
        })
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(())
}

#[tauri::command]
async fn gateway_remove(profile: String, name: String) -> Result<(), String> {
    alp_call_async(
        "host.gateway.remove",
        serde_json::json!({"profile": profile, "name": name}),
    )
    .await
}

#[tauri::command]
async fn mcp_add(
    profile: String,
    name: String,
    command: String,
    args: String,
    env: Vec<String>,
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
    alp_call_async(
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
async fn mcp_remove(profile: String, name: String) -> Result<(), String> {
    alp_call_async(
        "host.mcp.remove",
        serde_json::json!({"profile": profile, "name": name}),
    )
    .await
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
async fn voice_autoplay(profile: String, state: String) -> Result<(), String> {
    alp_call_async(
        "host.voice.autoplay",
        serde_json::json!({"profile": profile, "state": state}),
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

#[tauri::command]
async fn provider_set_key(
    profile: String, key: String, value: String,
) -> Result<(), String> {
    alp_call_async(
        "host.providers.set_key",
        serde_json::json!({"profile": profile, "key": key, "value": value}),
    )
    .await
}

#[tauri::command]
async fn provider_unset_key(profile: String, key: String) -> Result<(), String> {
    alp_call_async(
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
async fn schedules(profile: String) -> Result<serde_json::Value, String> {
    let result = tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.schedule.list",
            serde_json::json!({"profile": profile}),
        )
    })
    .await
    .map_err(|e| format!("schedules: {e}"))??;
    Ok(result.get("jobs").cloned().unwrap_or(serde_json::Value::Array(vec![])))
}

#[tauri::command]
async fn schedule_remove(profile: String, id: String) -> Result<(), String> {
    alp_call_async(
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
) -> Result<(), String> {
    alp_call_async(
        "host.schedule.set_paused",
        serde_json::json!({"profile": profile, "id": id, "paused": paused}),
    )
    .await
}

#[tauri::command]
async fn schedule_fire(profile: String, id: String) -> Result<(), String> {
    alp_call_async(
        "host.schedule.fire",
        serde_json::json!({"profile": profile, "id": id}),
    )
    .await
}

#[tauri::command]
async fn daemon_restart() -> Result<(), String> {
    alp_call_async("host.daemon.restart", serde_json::json!({})).await
}

#[tauri::command]
async fn resolve_ctx_window(profile: String, model: String) -> Result<u64, String> {
    let result = tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
            "host.model.ctx_window",
            serde_json::json!({ "profile": profile, "model": model }),
        )
    })
    .await
    .map_err(|e| format!("join: {e}"))??;
    Ok(result
        .get("ctx_window")
        .and_then(|v| v.as_u64())
        .unwrap_or(0))
}

#[tauri::command]
async fn pick_folder() -> Result<Option<String>, String> {
    let out = tauri::async_runtime::spawn_blocking(|| {
        Command::new("osascript")
            .args([
                "-e",
                "POSIX path of (choose folder with prompt \"Select workspace\")",
            ])
            .output()
    })
    .await
    .map_err(|e| format!("join: {e}"))?
    .map_err(|e| format!("osascript: {e}"))?;
    if !out.status.success() {
        return Ok(None);
    }
    let p = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if p.is_empty() {
        Ok(None)
    } else {
        Ok(Some(p.trim_end_matches('/').to_string()))
    }
}

#[tauri::command]
fn reveal_in_finder(path: String) -> Result<(), String> {
    Command::new("open")
        .args(["-R", &path])
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("open: {e}"))
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
async fn chat_cancel(profile: String) -> Result<(), String> {
    let request_id = {
        let map = active_chats().lock().unwrap();
        map.get(&profile).cloned()
    };
    let Some(request_id) = request_id else {
        return Ok(());
    };
    tauri::async_runtime::spawn_blocking(move || {
        host_client::call(
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
) {
    thread::spawn(move || {
        stream_chat(app, profile, session_id, rewrite_from_turn, text, model, request_id)
    });
}

fn stream_chat(
    app: AppHandle,
    profile: String,
    session_id: Option<String>,
    rewrite_from_turn: Option<usize>,
    text: String,
    model: Option<String>,
    request_id_opt: Option<String>,
) {
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
        .insert(profile.clone(), request_id.clone());

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

    let mut got_error = false;
    let mut got_interrupted = false;
    let mut resolved_id = String::new();
    let mut final_reply = String::new();
    let app_for_frames = app.clone();
    let rid_for_frames = request_id.clone();

    let result = host_client::call_stream("host.chat.send", params, |frame| {
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
        if map.get(&profile).map(|s| s.as_str()) == Some(&request_id) {
            map.remove(&profile);
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
        notifications::dispatch_session_done(&app, &profile, &resolved_id);
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
fn chat_events_since(
    profile: String,
    session_id: String,
    after_seq: Option<u64>,
    limit: Option<u64>,
) -> Result<serde_json::Value, String> {
    // Replay sidecar for the freeze case: when host.chat.send's stream socket dies mid-turn, the desktop polls this to backfill missed frames.
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
    host_client::call("host.chat.events_since", params)
}

#[tauri::command]
fn workgroup_transcript(
    profile: String,
    wg_id: String,
    after_seq: Option<u32>,
    limit: Option<u32>,
    tail: Option<bool>,
) -> Result<serde_json::Value, String> {
    // Default: tail=true, limit=200 — first-paint must be bounded so a workgroup with 10k posts doesn't ship megabytes over Tailscale. Subsequent fetches pass after_seq for incremental delta.
    let mut params = serde_json::json!({ "profile": profile, "wg_id": wg_id });
    if let Some(s) = after_seq {
        params["after_seq"] = serde_json::json!(s);
    } else if tail.unwrap_or(true) {
        params["tail"] = serde_json::json!(true);
    }
    params["limit"] = serde_json::json!(limit.unwrap_or(200));
    let result = host_client::call("host.workgroup.transcript", params)?;
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
        out.push(DecryptedMessage {
            seq,
            from,
            from_pubkey,
            body,
            at,
        });
    }
    let next_seq = result.get("next_seq").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
    Ok(serde_json::json!({
        "posts": out,
        "next_seq": next_seq,
    }))
}

#[tauri::command]
async fn workgroup_post(
    profile: String,
    wg_id: String,
    text: String,
) -> Result<String, String> {
    let params = serde_json::json!({ "profile": profile, "wg_id": wg_id, "text": text });
    let result = tauri::async_runtime::spawn_blocking(move || {
        host_client::call("host.workgroup.post", params)
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
fn tray_announce_update(app: AppHandle, available: bool, version: Option<String>) {
    tray::announce_update(&app, available, version.as_deref());
}

fn subscribe_daemon_events(app: AppHandle) {
    use std::collections::HashMap;
    use std::sync::{Arc, Mutex};

    use crate::event_dispatch::{classify_frame, SubscribeAction, SubscribeState};

    // One state object per (daemon connection). Keeps last_seq + the dedupe window. Survives loop iterations so reconnects retain the cursor.
    let states: Arc<Mutex<HashMap<String, SubscribeState>>> =
        Arc::new(Mutex::new(HashMap::new()));

    loop {
        let starting_id = host_client::active_connection_id();
        let app_for_frames = app.clone();
        let id_for_payload = starting_id.clone();
        let states_for_loop = Arc::clone(&states);
        let starting_id_for_match = starting_id.clone();

        let _ = host_client::call_stream_until(
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
                    .entry(starting_id_for_match.clone())
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
                                    let s = g.entry(starting_id_for_match.clone())
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
                                g.entry(starting_id_for_match.clone())
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
                            g.entry(starting_id_for_match.clone())
                                .or_insert_with(|| SubscribeState::new(1024))
                                .bump_seq(anchor);
                        }
                    }
                    SubscribeAction::Deliver { .. } => {
                        notifications::dispatch_daemon_frame(&app_for_frames, &frame);
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
        std::thread::sleep(std::time::Duration::from_secs(2));
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
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, shortcut, event| {
                    if event.state() == ShortcutState::Pressed && shortcut == &toggle_shortcut {
                        if let Some(window) = app.get_webview_window("main") {
                            match window.is_visible() {
                                Ok(true) => {
                                    let _ = window.hide();
                                    tray::set_window_visible(app, false);
                                }
                                _ => {
                                    let _ = window.show();
                                    let _ = window.set_focus();
                                    tray::set_window_visible(app, true);
                                }
                            }
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
                            host_client::ConnectionStatus::AuthFailed => "auth-failed",
                            host_client::ConnectionStatus::Unknown => "unknown",
                        },
                        "error": error,
                        "alpi_version": host_client::version_for(id),
                    }),
                );
                if matches!(status, host_client::ConnectionStatus::Offline) {
                    notifications::dispatch_daemon_disconnect(&app_for_status, id);
                }
            });
            spawn_background("probe-active-startup", host_client::probe_active);
            spawn_background("probe-active-loop", || loop {
                std::thread::sleep(std::time::Duration::from_secs(30));
                host_client::probe_active();
            });
            spawn_background("daemon-events", move || subscribe_daemon_events(app_handle));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
                tray::set_window_visible(window.app_handle(), false);
            }
        })
        .invoke_handler(tauri::generate_handler![
            profiles,
            profile_summaries,
            profile_detail,
            profile_tools,
            profile_skills,
            profile_skill_read,
            profile_memory,
            host_connections,
            host_connection_set_active,
            host_connection_forget,
            host_connection_add_remote,
            host_connections_probe_active,
            host_connections_probe_all,
            host_connection_probe,
            sessions,
            session_detail,
            workgroups,
            workgroup_transcript,
            workgroup_post,
            tts_synthesize,
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
            gateway_status,
            pick_folder,
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
            voice_autoplay,
            gateway_config,
            gateway_gmail_authorize,
            gateway_remove,
            mcp_add,
            mcp_remove,
            resolve_ctx_window,
            probe_gateways,
            devices_list,
            devices_generate,
            devices_revoke,
            devices_rename,
            network_status,
            network_set_advertised,
            network_restart_host_server,
            profile_storage,
            workgroup_members,
            workgroup_action,
            workgroup_update,
            workgroup_create,
            workgroup_add_member,
            tray_announce_update,
            set_active_view
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
