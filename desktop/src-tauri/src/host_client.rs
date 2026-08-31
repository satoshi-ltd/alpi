use std::collections::HashMap;
use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{IpAddr, SocketAddr, TcpStream, ToSocketAddrs};
#[cfg(unix)]
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex, OnceLock};
use std::time::{Duration, Instant};

use base64::Engine;
use flate2::{Decompress, FlushDecompress, Status};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha1::{Digest, Sha1};

#[cfg(unix)]
use crate::home::resolve_root;

#[cfg(not(unix))]
const LOCAL_UNSUPPORTED: &str =
    "local daemon connections aren't supported on Windows yet — pair a remote daemon over Tailscale";

// RPC timeouts stay generous — a busy daemon or slow Tailscale hop must not fail falsely (calls run off the main thread, so nothing freezes); dead-daemon detection belongs to the probes (2.5s local / 8s remote — a just-restarted daemon's warmup must not read as offline) and the stream keepalives (events ping 25s, chat heartbeat 5s → 75s = three missed pings).
const READ_TIMEOUT_LOCAL_SECS: u64 = 20;
const READ_TIMEOUT_REMOTE_SECS: u64 = 20;
// attachments.fetch ships up to 20 MiB as base64 JSON — a slow hop needs far more than the default RPC window.
const READ_TIMEOUT_FETCH_SECS: u64 = 60;
// The daemon updater permits 300s for the package manager, plus index and installer detection time.
const READ_TIMEOUT_UPDATE_SECS: u64 = 360;
const STREAM_READ_TIMEOUT_SECS: u64 = 75;
const WS_CONNECT_TIMEOUT_SECS: u64 = 4;
const WS_KEEPALIVE_IDLE_SECS: u64 = 30;
const WS_KEEPALIVE_INTERVAL_SECS: u64 = 10;
const PROBE_LOCAL_TIMEOUT_MS: u64 = 2500;
const PROBE_REMOTE_TIMEOUT_MS: u64 = 8000;
const PROBE_RETRY_DELAY_MS: u64 = 350;
// Sticky offline: tolerate transient blips on noisy Tailscale links.
const STICKY_OFFLINE_THRESHOLD: u32 = 2;
// Recent stream traffic vetoes request/probe-only offline transitions.
const STREAM_LIVENESS_WINDOW_SECS: u64 = 30;
// Bound concurrent request/response RPCs per remote connection so a Settings fan-out (or 10 remotes) can't open a burst of sockets at once. Local socket and streams are uncapped.
const MAX_INFLIGHT_PER_REMOTE: usize = 4;
// Window: ≥ the 25s inactive poll (so each pass reuses its socket) and < the daemon's ~40s ping deadline (20s idle ping + 20s pong timeout; reuse answers the queued ping on first read).
const POOL_IDLE_TTL_SECS: u64 = 30;
const CONNECTIONS_FILE: &str = "connections.json";
pub const LOCAL_ID: &str = "local";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionStatus {
    Unknown,
    Probing,
    Online,
    Offline,
    Disabled,
    AuthFailed,
}

impl ConnectionStatus {
    fn as_str(&self) -> &'static str {
        match self {
            ConnectionStatus::Unknown => "unknown",
            ConnectionStatus::Probing => "probing",
            ConnectionStatus::Online => "online",
            ConnectionStatus::Offline => "offline",
            ConnectionStatus::Disabled => "disabled",
            ConnectionStatus::AuthFailed => "auth-failed",
        }
    }
}

#[derive(Debug, Clone)]
struct StatusEntry {
    status: ConnectionStatus,
    error: Option<String>,
    consecutive_failures: u32,
    last_stream_frame: Option<Instant>,
    alpi_version: Option<String>,
    update_available: Option<String>,
    role: Option<String>,
}

impl Default for StatusEntry {
    fn default() -> Self {
        Self {
            status: ConnectionStatus::Unknown,
            error: None,
            consecutive_failures: 0,
            last_stream_frame: None,
            alpi_version: None,
            update_available: None,
            role: None,
        }
    }
}

fn status_map() -> &'static Mutex<HashMap<String, StatusEntry>> {
    static MAP: OnceLock<Mutex<HashMap<String, StatusEntry>>> = OnceLock::new();
    MAP.get_or_init(|| Mutex::new(HashMap::new()))
}

type StatusListener = Box<dyn Fn(&str, ConnectionStatus, Option<&str>) + Send + Sync>;

fn listeners() -> &'static Mutex<Vec<StatusListener>> {
    static LISTENERS: OnceLock<Mutex<Vec<StatusListener>>> = OnceLock::new();
    LISTENERS.get_or_init(|| Mutex::new(Vec::new()))
}

fn next_request_id() -> String {
    static NEXT_ID: AtomicU64 = AtomicU64::new(1);
    format!("tauri-{}", NEXT_ID.fetch_add(1, Ordering::Relaxed))
}

pub fn on_status_change<F>(f: F)
where
    F: Fn(&str, ConnectionStatus, Option<&str>) + Send + Sync + 'static,
{
    if let Ok(mut guard) = listeners().lock() {
        guard.push(Box::new(f));
    }
}

pub fn status_for(id: &str) -> (ConnectionStatus, Option<String>) {
    if let Ok(map) = status_map().lock() {
        if let Some(entry) = map.get(id) {
            return (entry.status, entry.error.clone());
        }
    }
    (ConnectionStatus::Unknown, None)
}

pub fn version_for(id: &str) -> Option<String> {
    if let Ok(map) = status_map().lock() {
        if let Some(entry) = map.get(id) {
            return entry.alpi_version.clone();
        }
    }
    None
}

pub fn role_for(id: &str) -> Option<String> {
    if let Ok(map) = status_map().lock() {
        if let Some(entry) = map.get(id) {
            return entry.role.clone();
        }
    }
    None
}

pub fn update_available_for(id: &str) -> Option<String> {
    if let Ok(map) = status_map().lock() {
        if let Some(entry) = map.get(id) {
            return entry.update_available.clone();
        }
    }
    None
}

fn set_update_available(id: &str, value: Option<String>) {
    let mut changed = false;
    if let Ok(mut map) = status_map().lock() {
        let entry = map.entry(id.to_string()).or_default();
        if entry.update_available != value {
            entry.update_available = value;
            changed = true;
        }
    }
    if changed {
        if let Ok(guard) = listeners().lock() {
            let (status, error) = status_for(id);
            for listener in guard.iter() {
                listener(id, status, error.as_deref());
            }
        }
    }
}

fn set_version(id: &str, version: Option<String>) {
    let mut changed = false;
    if let Ok(mut map) = status_map().lock() {
        let entry = map.entry(id.to_string()).or_default();
        if entry.alpi_version != version {
            entry.alpi_version = version;
            changed = true;
        }
    }
    if changed {
        if let Ok(guard) = listeners().lock() {
            let (status, error) = status_for(id);
            for listener in guard.iter() {
                listener(id, status, error.as_deref());
            }
        }
    }
}

fn set_role(id: &str, role: Option<String>) {
    let mut changed = false;
    if let Ok(mut map) = status_map().lock() {
        let entry = map.entry(id.to_string()).or_default();
        if entry.role != role {
            entry.role = role;
            changed = true;
        }
    }
    if changed {
        if let Ok(guard) = listeners().lock() {
            let (status, error) = status_for(id);
            for listener in guard.iter() {
                listener(id, status, error.as_deref());
            }
        }
    }
}

#[derive(Clone, Copy)]
enum StatusSource {
    General,
    Probe,
    Request,
    Stream,
}

fn stream_is_live(entry: &StatusEntry) -> bool {
    entry
        .last_stream_frame
        .is_some_and(|at| at.elapsed() < Duration::from_secs(STREAM_LIVENESS_WINDOW_SECS))
}

fn update_status(
    id: &str,
    status: ConnectionStatus,
    error: Option<String>,
    source: StatusSource,
) -> bool {
    let mut transitioned = false;
    if let Ok(mut map) = status_map().lock() {
        let entry = map.entry(id.to_string()).or_default();
        if matches!(source, StatusSource::Stream) {
            entry.last_stream_frame = Some(Instant::now());
            entry.consecutive_failures = 0;
            if matches!(entry.status, ConnectionStatus::AuthFailed | ConnectionStatus::Disabled) {
                return true;
            }
        }
        match status {
            ConnectionStatus::Offline if entry.status == ConnectionStatus::Online => {
                if matches!(source, StatusSource::Probe | StatusSource::Request)
                    && stream_is_live(entry)
                {
                    return false;
                }
                entry.consecutive_failures = entry.consecutive_failures.saturating_add(1);
                if entry.consecutive_failures < STICKY_OFFLINE_THRESHOLD {
                    return true;
                }
            }
            ConnectionStatus::Online => {
                entry.consecutive_failures = 0;
            }
            _ => {}
        }
        if entry.status != status || entry.error != error {
            entry.status = status;
            entry.error = error.clone();
            transitioned = true;
        }
    }
    if !transitioned {
        return true;
    }
    if let Ok(guard) = listeners().lock() {
        for listener in guard.iter() {
            listener(id, status, error.as_deref());
        }
    }
    true
}

// Online → Offline only flips after STICKY_OFFLINE_THRESHOLD consecutive failures.
fn set_status(id: &str, status: ConnectionStatus, error: Option<String>) {
    update_status(id, status, error, StatusSource::General);
}

fn note_stream_frame(id: &str) {
    update_status(id, ConnectionStatus::Online, None, StatusSource::Stream);
}

fn record_probe_failure(id: &str, status: ConnectionStatus, error: String) {
    if update_status(id, status, Some(error), StatusSource::Probe) {
        set_version(id, None);
    }
}

fn record_request_failure(id: &str, status: ConnectionStatus, error: String) {
    update_status(id, status, Some(error), StatusSource::Request);
}

fn classify_remote_error(err: &str) -> ConnectionStatus {
    if err.contains("connection-disabled") {
        ConnectionStatus::Disabled
    } else if err.contains("auth-failed") {
        ConnectionStatus::AuthFailed
    } else if err.starts_with("alp ") {
        ConnectionStatus::Online
    } else {
        ConnectionStatus::Offline
    }
}

fn classify_local_error(err: &str) -> ConnectionStatus {
    if err.starts_with("alp ") {
        ConnectionStatus::Online
    } else {
        ConnectionStatus::Offline
    }
}

// A genuine revoke (unknown/removed grant) authenticates as a bare auth-failed; transient reasons like a socket-identity change must not latch the connection revoked.
fn is_revocation_error(err: &str) -> bool {
    err.contains("auth-failed")
        && !err.contains("connection-disabled")
        && !err.contains("socket-identity-changed")
}

fn probe_timeout_for(conn: &HostConnection) -> Duration {
    match conn {
        HostConnection::Local { .. } => Duration::from_millis(PROBE_LOCAL_TIMEOUT_MS),
        HostConnection::Remote { .. } => Duration::from_millis(PROBE_REMOTE_TIMEOUT_MS),
    }
}

#[derive(Debug, Deserialize)]
struct ControlResponse {
    #[serde(default)]
    result: Option<Value>,
    #[serde(default)]
    error: Option<ControlError>,
}

#[derive(Debug, Deserialize)]
struct ControlError {
    #[serde(default)]
    code: i32,
    #[serde(default)]
    message: String,
    #[serde(default)]
    data: Option<Value>,
}

fn format_rpc_error(err: &ControlError) -> String {
    let detail = err
        .data
        .as_ref()
        .and_then(|d| {
            d.get("reason")
                .or_else(|| d.get("summary"))
                .or_else(|| d.get("detail"))
        })
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim();
    if detail.is_empty() {
        format!("alp {}: {}", err.code, err.message)
    } else {
        format!("alp {}: {} — {}", err.code, err.message, detail)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum HostConnection {
    Local {
        id: String,
        name: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        device_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        last_connected: Option<i64>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        last_role: Option<String>,
    },
    Remote {
        id: String,
        name: String,
        #[serde(rename = "url")]
        host: String,
        #[serde(default, skip_serializing_if = "is_zero_port")]
        port: u16,
        token: String,
        #[serde(default)]
        revoked: bool,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        device_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        last_connected: Option<i64>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        last_role: Option<String>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionsState {
    pub active_id: String,
    pub connections: Vec<HostConnection>,
}

impl Default for ConnectionsState {
    fn default() -> Self {
        Self {
            active_id: LOCAL_ID.to_string(),
            connections: vec![HostConnection::Local {
                id: LOCAL_ID.to_string(),
                name: "Local daemon".to_string(),
                device_id: None,
                last_connected: None,
                last_role: None,
            }],
        }
    }
}

impl HostConnection {
    pub fn id(&self) -> &str {
        match self {
            HostConnection::Local { id, .. } => id,
            HostConnection::Remote { id, .. } => id,
        }
    }

    fn is_revoked(&self) -> bool {
        matches!(self, HostConnection::Remote { revoked: true, .. })
    }

    pub fn device_id(&self) -> Option<&str> {
        match self {
            HostConnection::Local { device_id, .. } => device_id.as_deref(),
            HostConnection::Remote { device_id, .. } => device_id.as_deref(),
        }
    }

    pub fn set_device_id(&mut self, value: Option<String>) {
        match self {
            HostConnection::Local { device_id, .. } => *device_id = value,
            HostConnection::Remote { device_id, .. } => *device_id = value,
        }
    }

    pub fn set_last_connected(&mut self, value: Option<i64>) {
        match self {
            HostConnection::Local { last_connected, .. } => *last_connected = value,
            HostConnection::Remote { last_connected, .. } => *last_connected = value,
        }
    }

    pub fn last_role(&self) -> Option<&str> {
        match self {
            HostConnection::Local { last_role, .. } => last_role.as_deref(),
            HostConnection::Remote { last_role, .. } => last_role.as_deref(),
        }
    }

    pub fn set_last_role(&mut self, value: Option<String>) {
        match self {
            HostConnection::Local { last_role, .. } => *last_role = value,
            HostConnection::Remote { last_role, .. } => *last_role = value,
        }
    }

    fn with_token_redacted(&self) -> Value {
        let (status, error) = status_for(self.id());
        let alpi_version = version_for(self.id());
        let update_available = update_available_for(self.id());
        let role = role_for(self.id()).or_else(|| self.last_role().map(str::to_string));
        match self {
            HostConnection::Local { id, name, device_id, last_connected, .. } => {
                json!({
                    "id": id,
                    "name": name,
                    "kind": "local",
                    "status": status.as_str(),
                    "error": error,
                    "alpi_version": alpi_version,
                    "update_available": update_available,
                    "device_id": device_id,
                    "role": role,
                    "last_connected": last_connected,
                })
            }
            HostConnection::Remote {
                id,
                name,
                host,
                port,
                token,
                revoked,
                device_id,
                last_connected,
                ..
            } => {
                let endpoint_url = parse_remote_endpoint(host, *port)
                    .map(|endpoint| endpoint.url)
                    .unwrap_or_else(|_| format!("ws://{host}:{port}"));
                json!({
                    "id": id,
                    "name": name,
                    "kind": "remote",
                    "url": endpoint_url,
                    "token_id": token.chars().rev().take(8).collect::<String>().chars().rev().collect::<String>(),
                    "revoked": revoked,
                    "status": status.as_str(),
                    "error": error,
                    "alpi_version": alpi_version,
                    "update_available": update_available,
                    "device_id": device_id,
                    "role": role,
                    "last_connected": last_connected,
                })
            }
        }
    }
}

fn is_zero_port(port: &u16) -> bool {
    *port == 0
}

#[cfg(test)]
fn config_dir_override() -> &'static Mutex<Option<PathBuf>> {
    static OVERRIDE: OnceLock<Mutex<Option<PathBuf>>> = OnceLock::new();
    OVERRIDE.get_or_init(|| Mutex::new(None))
}

fn connections_dir() -> Result<PathBuf, String> {
    #[cfg(test)]
    if let Ok(guard) = config_dir_override().lock() {
        if let Some(dir) = guard.as_ref() {
            return Ok(dir.clone());
        }
    }
    dirs::config_dir()
        .map(|p| p.join("alpi-desktop"))
        .ok_or_else(|| "cannot resolve config dir".to_string())
}

fn connections_path() -> Result<PathBuf, String> {
    Ok(connections_dir()?.join(CONNECTIONS_FILE))
}

fn decode_connections(text: &str) -> Result<ConnectionsState, serde_json::Error> {
    let mut value: Value = serde_json::from_str(text)?;
    if let Some(rows) = value.get_mut("connections").and_then(Value::as_array_mut) {
        for row in rows {
            let Some(object) = row.as_object_mut() else {
                continue;
            };
            if object.get("kind").and_then(Value::as_str) != Some("remote") {
                continue;
            }
            if object.contains_key("url") {
                object.remove("host");
            } else if let Some(host) = object.remove("host") {
                object.insert("url".to_string(), host);
            }
        }
    }
    serde_json::from_value(value)
}

fn connections_disk_value(state: &ConnectionsState) -> Result<Value, String> {
    let mut value = serde_json::to_value(state).map_err(|e| format!("encode: {e}"))?;
    if let Some(rows) = value.get_mut("connections").and_then(Value::as_array_mut) {
        for row in rows {
            let Some(object) = row.as_object_mut() else {
                continue;
            };
            if object.get("kind").and_then(Value::as_str) != Some("remote") {
                continue;
            }
            let Some(url) = object.get("url").and_then(Value::as_str) else {
                continue;
            };
            let legacy_port = object.get("port").and_then(Value::as_u64).unwrap_or(0) as u16;
            let Ok(endpoint) = parse_remote_endpoint(url, legacy_port) else {
                continue;
            };
            object.insert("host".to_string(), Value::String(endpoint.host));
            object.insert("port".to_string(), json!(endpoint.port));
        }
    }
    Ok(value)
}

pub fn load_connections() -> ConnectionsState {
    let path = match connections_path() {
        Ok(p) => p,
        Err(_) => return ConnectionsState::default(),
    };
    let text = match fs::read_to_string(path) {
        Ok(t) => t,
        Err(_) => return ConnectionsState::default(),
    };
    let mut state: ConnectionsState = match decode_connections(&text) {
        Ok(s) => s,
        Err(_) => return ConnectionsState::default(),
    };
    ensure_local(&mut state);
    if !state
        .connections
        .iter()
        .any(|c| c.id() == state.active_id && !c.is_revoked())
    {
        state.active_id = LOCAL_ID.to_string();
    }
    state
}

fn ensure_local(state: &mut ConnectionsState) {
    if state.connections.iter().any(|c| c.id() == LOCAL_ID) {
        return;
    }
    state.connections.insert(0, HostConnection::Local {
        id: LOCAL_ID.to_string(),
        name: "Local daemon".to_string(),
        device_id: None,
        last_connected: None,
        last_role: None,
    });
}

pub fn active_subscription_key() -> Option<String> {
    let state = load_connections();
    let active = state.connections.iter().find(|c| c.id() == state.active_id)?;
    active.device_id().map(|d| format!("daemon:{d}"))
}

fn persist_device_id(connection_id: &str, device_id: &str) {
    mutate_connections(|state| {
        for conn in state.connections.iter_mut() {
            if conn.id() == connection_id {
                if conn.device_id() != Some(device_id) {
                    conn.set_device_id(Some(device_id.to_string()));
                    return true;
                }
                break;
            }
        }
        false
    });
}

fn persist_role(connection_id: &str, role: Option<String>) {
    mutate_connections(|state| {
        for conn in state.connections.iter_mut() {
            if conn.id() == connection_id {
                if conn.last_role().map(str::to_string) != role {
                    conn.set_last_role(role.clone());
                    return true;
                }
                break;
            }
        }
        false
    });
}

// Live probed role wins; persisted last_role is the cold-start fallback so pollers/fetch gates know a connection's role before it is re-probed.
pub fn effective_role(conn: &HostConnection) -> Option<String> {
    role_for(conn.id()).or_else(|| conn.last_role().map(str::to_string))
}

fn persist_last_connected(connection_id: &str) {
    mutate_connections(|state| {
        for conn in state.connections.iter_mut() {
            if conn.id() == connection_id {
                conn.set_last_connected(Some(now_unix()));
                return true;
            }
        }
        false
    });
}

#[cfg(unix)]
fn open_private(path: &std::path::Path) -> std::io::Result<fs::File> {
    use std::os::unix::fs::OpenOptionsExt;
    fs::OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .mode(0o600)
        .open(path)
}

#[cfg(not(unix))]
fn open_private(path: &std::path::Path) -> std::io::Result<fs::File> {
    fs::OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .open(path)
}

fn save_connections(state: &ConnectionsState) -> Result<(), String> {
    invalidate_active_id_cache();
    let dir = connections_dir()?;
    fs::create_dir_all(&dir).map_err(|e| format!("create {}: {e}", dir.display()))?;
    let path = connections_path()?;
    let tmp = path.with_extension("json.tmp");
    let value = connections_disk_value(state)?;
    let text = serde_json::to_string_pretty(&value).map_err(|e| format!("encode: {e}"))?;
    let mut f = open_private(&tmp)
        .map_err(|e| format!("open {}: {e}", tmp.display()))?;
    f.write_all(text.as_bytes())
        .map_err(|e| format!("write {}: {e}", tmp.display()))?;
    f.flush().ok();
    fs::rename(&tmp, &path).map_err(|e| format!("rename {}: {e}", path.display()))
}

fn connections_mutex() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}

// Every connections.json writer runs load→mutate→save under this one lock — a background probe's metadata write must never interleave with (and lose to) a concurrent activate/add/forget/revoke. Reads stay lock-free; the atomic rename makes torn reads impossible.
fn mutate_connections(f: impl FnOnce(&mut ConnectionsState) -> bool) {
    let _guard = connections_mutex().lock().unwrap_or_else(|e| e.into_inner());
    let mut state = load_connections();
    if f(&mut state) {
        let _ = save_connections(&state);
    }
}

fn try_mutate_connections<T>(
    f: impl FnOnce(&mut ConnectionsState) -> Result<T, String>,
) -> Result<T, String> {
    let _guard = connections_mutex().lock().unwrap_or_else(|e| e.into_inner());
    let mut state = load_connections();
    let out = f(&mut state)?;
    save_connections(&state)?;
    Ok(out)
}

fn now_unix() -> i64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn display_rank(conn: &HostConnection, active_id: &str) -> u8 {
    if conn.id() == active_id {
        0
    } else if conn.id() == LOCAL_ID {
        1
    } else {
        2
    }
}

// Stable rank, never last_connected — a live probe must not reshuffle the open list.
fn ordered_for_display<'a>(
    conns: &'a [HostConnection],
    active_id: &str,
) -> Vec<&'a HostConnection> {
    let mut out: Vec<&HostConnection> = conns.iter().collect();
    out.sort_by_key(|c| display_rank(c, active_id));
    out
}

pub fn connections_for_ui() -> Value {
    let state = load_connections();
    json!({
        "active_id": state.active_id,
        "connections": ordered_for_display(&state.connections, &state.active_id)
            .iter()
            .map(|c| c.with_token_redacted())
            .collect::<Vec<_>>(),
    })
}

pub fn set_active_connection(id: String) -> Result<(), String> {
    try_mutate_connections(|state| {
        let conn = state
            .connections
            .iter()
            .find(|c| c.id() == id)
            .ok_or_else(|| format!("unknown connection: {id}"))?;
        if conn.is_revoked() {
            return Err(format!("connection is revoked: {id}"));
        }
        state.active_id = id;
        Ok(())
    })
}

pub fn forget_connection(id: String) -> Result<(), String> {
    if id == LOCAL_ID {
        return Err("local connection cannot be removed".to_string());
    }
    try_mutate_connections(|state| {
        state.connections.retain(|c| c.id() != id);
        if state.active_id == id {
            state.active_id = LOCAL_ID.to_string();
        }
        Ok(())
    })?;
    if let Ok(mut map) = status_map().lock() {
        map.remove(&id);
    }
    purge_ws_pool(&id);
    Ok(())
}

pub fn add_remote_connection(
    name: String,
    url: String,
    token: String,
) -> Result<String, String> {
    if !url.trim().starts_with("ws://") && !url.trim().starts_with("wss://") {
        return Err("remote URL must use ws:// or wss://".to_string());
    }
    let endpoint = parse_remote_endpoint(url.trim(), 0)?;
    if token.trim().is_empty() {
        return Err("token is required".to_string());
    }
    let id = format!(
        "remote-{}-{}-{}",
        if endpoint.secure { "wss" } else { "ws" },
        endpoint.host.replace(|c: char| !c.is_ascii_alphanumeric(), "-"),
        endpoint.port,
    );
    try_mutate_connections(|state| {
        state.connections.retain(|c| c.id() != id);
        state.connections.push(HostConnection::Remote {
            id: id.clone(),
            name: if name.trim().is_empty() {
                endpoint.host.clone()
            } else {
                name.trim().to_string()
            },
            host: endpoint.url.clone(),
            port: 0,
            token: token.trim().to_string(),
            revoked: false,
            device_id: None,
            last_connected: None,
            last_role: None,
        });
        state.active_id = id.clone();
        Ok(())
    })?;
    purge_ws_pool(&id);
    Ok(id)
}

pub fn exchange_and_add_remote_connection(
    name: String,
    url: String,
    pairing_token: String,
    device_name: String,
    app_version: String,
) -> Result<String, String> {
    let endpoint = parse_remote_endpoint(url.trim(), 0)?;
    if pairing_token.trim().is_empty() {
        return Err("pairing token is required".to_string());
    }
    let mut ws = WsClient::connect(
        &endpoint.url,
        0,
        Duration::from_secs(WS_CONNECT_TIMEOUT_SECS),
        Duration::from_secs(READ_TIMEOUT_REMOTE_SECS),
    )?;
    let id = next_request_id();
    let result = ws.request(
        &id,
        &json!({
            "id": id,
            "method": "host.connections.exchange_pairing",
            "params": {
                "pairing_token": pairing_token,
                "client": "desktop",
                "name": device_name,
                "app_version": app_version,
            },
        }),
    )?;
    let token = result
        .get("token")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| "pairing exchange returned no device token".to_string())?;
    let connection_id = add_remote_connection(name, endpoint.url, token.to_string())?;
    if let Some(device_id) = result.get("device_id").and_then(Value::as_str) {
        persist_device_id(&connection_id, device_id);
    }
    persist_role(
        &connection_id,
        result.get("role").and_then(Value::as_str).map(str::to_string),
    );
    Ok(connection_id)
}

pub fn mark_connection_revoked(id: &str) {
    mutate_connections(|state| {
        let mut changed = false;
        for c in &mut state.connections {
            if let HostConnection::Remote { id: cid, revoked, .. } = c {
                if cid == id && !*revoked {
                    *revoked = true;
                    changed = true;
                }
            }
        }
        if state.active_id == id {
            state.active_id = LOCAL_ID.to_string();
            changed = true;
        }
        changed
    });
    purge_ws_pool(id);
}

pub fn clear_connection_revoked(id: &str) {
    mutate_connections(|state| {
        let mut changed = false;
        for c in &mut state.connections {
            if let HostConnection::Remote { id: cid, revoked, .. } = c {
                if cid == id && *revoked {
                    *revoked = false;
                    changed = true;
                }
            }
        }
        changed
    });
}

fn active_id_cache() -> &'static Mutex<Option<String>> {
    static CACHE: OnceLock<Mutex<Option<String>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(None))
}

// Cached in memory — hot path on every daemon event frame.
pub fn active_connection_id() -> String {
    if let Ok(guard) = active_id_cache().lock() {
        if let Some(id) = guard.as_ref() {
            return id.clone();
        }
    }
    let id = load_connections().active_id;
    if let Ok(mut guard) = active_id_cache().lock() {
        *guard = Some(id.clone());
    }
    id
}

fn invalidate_active_id_cache() {
    if let Ok(mut guard) = active_id_cache().lock() {
        *guard = None;
    }
}

fn active_connection() -> HostConnection {
    let state = load_connections();
    state
        .connections
        .iter()
        .find(|c| c.id() == state.active_id)
        .cloned()
        .unwrap_or(HostConnection::Local {
            id: LOCAL_ID.to_string(),
            name: "Local daemon".to_string(),
            device_id: None,
            last_connected: None,
            last_role: None,
        })
}

#[cfg(unix)]
fn socket_path() -> Result<PathBuf, String> {
    let root = resolve_root().ok_or_else(|| "cannot resolve ~/.alpi".to_string())?;
    Ok(root.join("host").join("host.sock"))
}

fn connection_by_id(connection_id: &str) -> Option<HostConnection> {
    load_connections()
        .connections
        .into_iter()
        .find(|c| c.id() == connection_id)
}

struct RemoteGate {
    inflight: Mutex<usize>,
    cv: Condvar,
}

fn remote_gates() -> &'static Mutex<HashMap<String, Arc<RemoteGate>>> {
    static GATES: OnceLock<Mutex<HashMap<String, Arc<RemoteGate>>>> = OnceLock::new();
    GATES.get_or_init(|| Mutex::new(HashMap::new()))
}

fn remote_gate(connection_id: &str) -> Arc<RemoteGate> {
    let mut map = remote_gates().lock().expect("remote gate map poisoned");
    Arc::clone(
        map.entry(connection_id.to_string())
            .or_insert_with(|| Arc::new(RemoteGate { inflight: Mutex::new(0), cv: Condvar::new() })),
    )
}

struct RemoteSlot(Arc<RemoteGate>);

impl Drop for RemoteSlot {
    fn drop(&mut self) {
        let mut n = self.0.inflight.lock().expect("remote gate poisoned");
        *n = n.saturating_sub(1);
        self.0.cv.notify_one();
    }
}

// Blocks the calling spawn_blocking thread until this connection is under MAX_INFLIGHT_PER_REMOTE; the guard releases the slot on drop. Never call on the async loop.
fn acquire_remote_slot(connection_id: &str) -> RemoteSlot {
    let gate = remote_gate(connection_id);
    let mut n = gate.inflight.lock().expect("remote gate poisoned");
    while *n >= MAX_INFLIGHT_PER_REMOTE {
        n = gate.cv.wait(n).expect("remote gate poisoned");
    }
    *n += 1;
    drop(n);
    RemoteSlot(Arc::clone(&gate))
}

type PoolEndpoint = (String, u16, String);

struct PoolEntry<T> {
    conn: T,
    endpoint: PoolEndpoint,
    idle_since: Instant,
}

struct WsPool<T> {
    max_per_key: usize,
    idle_ttl: Duration,
    entries: HashMap<String, Vec<PoolEntry<T>>>,
}

impl<T> WsPool<T> {
    fn new(max_per_key: usize, idle_ttl: Duration) -> Self {
        Self {
            max_per_key,
            idle_ttl,
            entries: HashMap::new(),
        }
    }

    // LIFO: the most-recently-idle socket is the least likely to carry an unanswered daemon ping.
    fn checkout(&mut self, key: &str, endpoint: &PoolEndpoint, now: Instant) -> Option<T> {
        let list = self.entries.get_mut(key)?;
        while let Some(entry) = list.pop() {
            if now.duration_since(entry.idle_since) < self.idle_ttl && &entry.endpoint == endpoint {
                return Some(entry.conn);
            }
        }
        None
    }

    fn checkin(&mut self, key: &str, endpoint: PoolEndpoint, conn: T, now: Instant) {
        let list = self.entries.entry(key.to_string()).or_default();
        if list.len() < self.max_per_key {
            list.push(PoolEntry {
                conn,
                endpoint,
                idle_since: now,
            });
        }
    }

    fn purge(&mut self, key: &str) {
        self.entries.remove(key);
    }
}

fn ws_pool() -> &'static Mutex<WsPool<WsClient>> {
    static POOL: OnceLock<Mutex<WsPool<WsClient>>> = OnceLock::new();
    POOL.get_or_init(|| {
        Mutex::new(WsPool::new(
            MAX_INFLIGHT_PER_REMOTE,
            Duration::from_secs(POOL_IDLE_TTL_SECS),
        ))
    })
}

pub fn purge_ws_pool(connection_id: &str) {
    if let Ok(mut pool) = ws_pool().lock() {
        pool.purge(connection_id);
    }
}

// Only an "alp <code>: …" RPC error proves clean framing; any transport/decode error may leave a half-read frame on the socket.
fn reusable_after_error(err: &str) -> bool {
    err.starts_with("alp ")
}

pub fn call(method: &str, params: Value) -> Result<Value, String> {
    call_conn(&active_connection(), method, params, None)
}

// Same as `call`, but routed to a specific connection regardless of which is active.
pub fn call_for(connection_id: &str, method: &str, params: Value) -> Result<Value, String> {
    let conn = connection_by_id(connection_id)
        .ok_or_else(|| format!("unknown connection: {connection_id}"))?;
    call_conn(&conn, method, params, None)
}

pub fn call_for_update(connection_id: &str, method: &str, params: Value) -> Result<Value, String> {
    let conn = connection_by_id(connection_id)
        .ok_or_else(|| format!("unknown connection: {connection_id}"))?;
    call_conn_with_retry(
        &conn,
        method,
        params,
        Some(Duration::from_secs(READ_TIMEOUT_UPDATE_SECS)),
        false,
    )
}

pub fn call_fetch(method: &str, params: Value) -> Result<Value, String> {
    call_conn(
        &active_connection(),
        method,
        params,
        Some(Duration::from_secs(READ_TIMEOUT_FETCH_SECS)),
    )
}

pub fn call_for_fetch(connection_id: &str, method: &str, params: Value) -> Result<Value, String> {
    let conn = connection_by_id(connection_id)
        .ok_or_else(|| format!("unknown connection: {connection_id}"))?;
    call_conn(
        &conn,
        method,
        params,
        Some(Duration::from_secs(READ_TIMEOUT_FETCH_SECS)),
    )
}

fn read_timeout_for(conn: &HostConnection, over: Option<Duration>) -> Duration {
    over.unwrap_or_else(|| match conn {
        HostConnection::Local { .. } => Duration::from_secs(READ_TIMEOUT_LOCAL_SECS),
        HostConnection::Remote { .. } => Duration::from_secs(READ_TIMEOUT_REMOTE_SECS),
    })
}

const SLOW_RPC_LOG_MS: u128 = 1000;

fn call_conn(
    conn: &HostConnection,
    method: &str,
    params: Value,
    read_timeout: Option<Duration>,
) -> Result<Value, String> {
    call_conn_with_retry(conn, method, params, read_timeout, true)
}

fn call_conn_with_retry(
    conn: &HostConnection,
    method: &str,
    params: Value,
    read_timeout: Option<Duration>,
    retry_remote: bool,
) -> Result<Value, String> {
    let id = conn.id().to_string();
    let timeout = read_timeout_for(conn, read_timeout);
    let started = Instant::now();
    let result = match conn {
        HostConnection::Local { .. } => call_local_inner(method, params, timeout),
        HostConnection::Remote {
            host, port, token, ..
        } => {
            let _slot = acquire_remote_slot(&id);
            if retry_remote {
                call_remote_inner(&id, host, *port, token, method, params, timeout)
            } else {
                call_remote_single(host, *port, token, method, params, timeout)
            }
        }
    };
    let elapsed = started.elapsed().as_millis();
    // Elapsed includes time queued on the per-connection slot gate — exactly the wait the user experiences.
    if elapsed >= SLOW_RPC_LOG_MS {
        eprintln!("[slow-rpc] {method} on {id}: {elapsed}ms (ok={})", result.is_ok());
    }
    match &result {
        Ok(_) => set_status(&id, ConnectionStatus::Online, None),
        Err(e) => {
            let next = match conn {
                HostConnection::Local { .. } => classify_local_error(e),
                HostConnection::Remote { .. } => {
                    let cls = classify_remote_error(e);
                    if is_revocation_error(e) {
                        mark_connection_revoked(&id);
                    }
                    cls
                }
            };
            record_request_failure(&id, next, e.clone());
        }
    }
    result
}

#[cfg(not(unix))]
fn call_local_inner(_method: &str, _params: Value, _timeout: Duration) -> Result<Value, String> {
    Err(LOCAL_UNSUPPORTED.to_string())
}

#[cfg(unix)]
fn call_local_inner(method: &str, params: Value, timeout: Duration) -> Result<Value, String> {
    let path = socket_path()?;
    if !path.exists() {
        return Err(format!(
            "alpi daemon socket not found at {} — is the daemon running?",
            path.display()
        ));
    }
    let mut stream = UnixStream::connect(&path)
        .map_err(|e| format!("connect {}: {e}", path.display()))?;
    stream
        .set_read_timeout(Some(timeout))
        .map_err(|e| format!("set timeout: {e}"))?;

    let body = json!({
        "id": "tauri-1",
        "method": method,
        "params": params,
    });
    let mut line = serde_json::to_string(&body).map_err(|e| format!("encode: {e}"))?;
    line.push('\n');
    stream
        .write_all(line.as_bytes())
        .map_err(|e| format!("write: {e}"))?;
    stream.flush().ok();

    let mut reader = BufReader::new(stream);
    let mut response_line = String::new();
    reader
        .read_line(&mut response_line)
        .map_err(|e| format!("read: {e}"))?;
    if response_line.is_empty() {
        return Err("daemon closed connection without responding".to_string());
    }
    let response: ControlResponse = serde_json::from_str(response_line.trim_end())
        .map_err(|e| format!("decode: {e}"))?;
    if let Some(err) = response.error {
        return Err(format_rpc_error(&err));
    }
    response
        .result
        .ok_or_else(|| "daemon returned neither result nor error".to_string())
}

pub fn call_stream<F>(
    method: &str,
    params: Value,
    mut on_frame: F,
) -> Result<(), String>
where
    F: FnMut(Value),
{
    call_stream_until(method, params, move |frame| {
        on_frame(frame);
        true
    })
}

// on_frame returns false to break the stream early.
pub fn call_stream_until<F>(
    method: &str,
    params: Value,
    on_frame: F,
) -> Result<(), String>
where
    F: FnMut(Value) -> bool,
{
    let conn = active_connection();
    let id = conn.id().to_string();
    let result = match &conn {
        HostConnection::Local { .. } => call_stream_local(&id, method, params, on_frame),
        HostConnection::Remote {
            id: _,
            host,
            port,
            token,
            ..
        } => call_stream_remote(&id, host, *port, token, method, params, on_frame),
    };
    match &result {
        Ok(()) => set_status(&id, ConnectionStatus::Online, None),
        Err(e) => {
            let next = match &conn {
                HostConnection::Local { .. } => classify_local_error(e),
                HostConnection::Remote { .. } => classify_remote_error(e),
            };
            set_status(&id, next, Some(e.clone()));
        }
    }
    result
}

#[cfg(not(unix))]
fn call_stream_local<F>(
    _id: &str,
    _method: &str,
    _params: Value,
    _on_frame: F,
) -> Result<(), String>
where
    F: FnMut(Value) -> bool,
{
    Err(LOCAL_UNSUPPORTED.to_string())
}

#[cfg(unix)]
fn call_stream_local<F>(
    id: &str,
    method: &str,
    params: Value,
    mut on_frame: F,
) -> Result<(), String>
where
    F: FnMut(Value) -> bool,
{
    let path = socket_path()?;
    if !path.exists() {
        return Err(format!(
            "alpi daemon socket not found at {} — is the daemon running?",
            path.display()
        ));
    }
    let mut stream = UnixStream::connect(&path)
        .map_err(|e| format!("connect {}: {e}", path.display()))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(STREAM_READ_TIMEOUT_SECS)))
        .map_err(|e| format!("set timeout: {e}"))?;

    let body = json!({
        "id": "tauri-stream",
        "method": method,
        "params": params,
    });
    let mut line = serde_json::to_string(&body).map_err(|e| format!("encode: {e}"))?;
    line.push('\n');
    stream
        .write_all(line.as_bytes())
        .map_err(|e| format!("write: {e}"))?;
    stream.flush().ok();

    let reader = BufReader::new(stream);
    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(e) => return Err(format!("read: {e}")),
        };
        if line.trim().is_empty() {
            continue;
        }
        let frame: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(_) => continue,
        };
        note_stream_frame(id);
        if !on_frame(frame) {
            break;
        }
    }
    Ok(())
}

fn call_remote_inner(
    connection_id: &str,
    host: &str,
    port: u16,
    token: &str,
    method: &str,
    params: Value,
    timeout: Duration,
) -> Result<Value, String> {
    retry_remote(|| call_remote_once(connection_id, host, port, token, method, params.clone(), timeout))
}

fn call_remote_single(
    host: &str,
    port: u16,
    token: &str,
    method: &str,
    params: Value,
    timeout: Duration,
) -> Result<Value, String> {
    let mut ws = WsClient::connect(
        host,
        port,
        Duration::from_secs(WS_CONNECT_TIMEOUT_SECS),
        timeout,
    )?;
    let id = next_request_id();
    ws.request(
        &id,
        &json!({
            "id": id,
            "method": method,
            "params": with_auth(params, token),
        }),
    )
}

fn retry_remote<F>(mut attempt: F) -> Result<Value, String>
where
    F: FnMut() -> Result<Value, String>,
{
    for i in 0..2 {
        match attempt() {
            Ok(value) => return Ok(value),
            Err(e) if i == 0 && should_retry_remote_ws(&e) => continue,
            Err(e) => return Err(e),
        }
    }
    Err("remote websocket retry exhausted".to_string())
}

fn should_retry_remote_ws(err: &str) -> bool {
    !err.contains("auth-failed")
        && (err.starts_with("websocket ")
            || err.starts_with("connect ")
            || err.starts_with("set read timeout")
            || err.starts_with("set write timeout"))
}

fn call_remote_once(
    connection_id: &str,
    host: &str,
    port: u16,
    token: &str,
    method: &str,
    params: Value,
    timeout: Duration,
) -> Result<Value, String> {
    let endpoint: PoolEndpoint = (host.to_string(), port, token.to_string());
    let request = |ws: &mut WsClient| {
        let id = next_request_id();
        ws.request(
            &id,
            &json!({
                "id": id,
                "method": method,
                "params": with_auth(params.clone(), token),
            }),
        )
    };
    let pooled = ws_pool()
        .lock()
        .ok()
        .and_then(|mut pool| pool.checkout(connection_id, &endpoint, Instant::now()));
    if let Some(mut ws) = pooled {
        if ws.set_timeouts(timeout).is_ok() {
            let result = request(&mut ws);
            match &result {
                Ok(_) => {
                    pool_checkin(connection_id, endpoint, ws);
                    return result;
                }
                Err(e) if reusable_after_error(e) => {
                    pool_checkin(connection_id, endpoint, ws);
                    return result;
                }
                // A dead pooled socket means the daemon likely restarted: drop the whole pool and fall through to a fresh connect within this same attempt.
                Err(_) => purge_ws_pool(connection_id),
            }
        } else {
            purge_ws_pool(connection_id);
        }
    }
    let mut ws = WsClient::connect(
        host,
        port,
        Duration::from_secs(WS_CONNECT_TIMEOUT_SECS),
        timeout,
    )?;
    let result = request(&mut ws);
    let healthy = match &result {
        Ok(_) => true,
        Err(e) => reusable_after_error(e),
    };
    if healthy {
        pool_checkin(connection_id, endpoint, ws);
    }
    result
}

fn pool_checkin(connection_id: &str, endpoint: PoolEndpoint, ws: WsClient) {
    if let Ok(mut pool) = ws_pool().lock() {
        pool.checkin(connection_id, endpoint, ws, Instant::now());
    }
}

fn call_stream_remote<F>(
    connection_id: &str,
    host: &str,
    port: u16,
    token: &str,
    method: &str,
    params: Value,
    mut on_frame: F,
) -> Result<(), String>
where
    F: FnMut(Value) -> bool,
{
    let mut ws = WsClient::connect(
        host,
        port,
        Duration::from_secs(WS_CONNECT_TIMEOUT_SECS),
        Duration::from_secs(STREAM_READ_TIMEOUT_SECS),
    )?;
    let id = "tauri-stream";
    ws.send_json(&json!({
        "id": id,
        "method": method,
        "params": with_auth(params, token),
    }))?;
    loop {
        let text = ws.read_text()?;
        if !frame_matches_id(&text, id) {
            continue;
        }
        let frame: Value = match serde_json::from_str(&text) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let done = frame
            .get("event")
            .and_then(|v| v.as_str())
            .map(|ev| matches!(ev, "done" | "error" | "interrupted"))
            .unwrap_or(false)
            || frame.get("error").is_some();
        let auth_error = frame.get("error").and_then(|err| {
            let code = err.get("code")?.as_i64()?;
            let message = err.get("message")?.as_str()?;
            if code != -32000 || message != "auth-failed" {
                return None;
            }
            let reason = err
                .get("data")
                .and_then(|data| data.get("reason"))
                .and_then(|value| value.as_str());
            Some(reason.unwrap_or("").to_string())
        });
        if let Some(reason) = auth_error {
            if reason == "connection-disabled" {
                return Err("alp -32000: auth-failed — connection-disabled".to_string());
            }
            // A transient socket-identity change must not latch revoked; a bare auth-failed (unknown/removed grant) still does.
            if reason != "socket-identity-changed" {
                mark_connection_revoked(connection_id);
            }
            let suffix = if reason.is_empty() {
                String::new()
            } else {
                format!(" — {reason}")
            };
            return Err(format!("alp -32000: auth-failed{suffix}"));
        }
        note_stream_frame(connection_id);
        let keep_going = on_frame(frame);
        if done || !keep_going {
            break;
        }
    }
    Ok(())
}

fn with_auth(mut params: Value, token: &str) -> Value {
    if !params.is_object() {
        params = json!({});
    }
    if let Some(obj) = params.as_object_mut() {
        obj.insert("auth_token".to_string(), Value::String(token.to_string()));
    }
    params
}

fn frame_matches_id(text: &str, id: &str) -> bool {
    serde_json::from_str::<Value>(text)
        .ok()
        .and_then(|v| v.get("id").and_then(|x| x.as_str()).map(|s| s == id))
        .unwrap_or(false)
}

fn is_valid_hostname(host: &str) -> bool {
    let host = host.strip_suffix('.').unwrap_or(host);
    if host.is_empty() || host.len() > 253 {
        return false;
    }
    host.split('.').all(|label| {
        !label.is_empty()
            && label.len() <= 63
            && !label.starts_with('-')
            && !label.ends_with('-')
            && label.chars().all(|c| c.is_ascii_alphanumeric() || c == '-')
    })
}

fn is_valid_host(host: &str) -> bool {
    host.parse::<IpAddr>().is_ok() || is_valid_hostname(host)
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RemoteEndpoint {
    url: String,
    host: String,
    port: u16,
    secure: bool,
}

fn parse_remote_endpoint(value: &str, legacy_port: u16) -> Result<RemoteEndpoint, String> {
    let value = value.trim();
    let (secure, authority) = if let Some(rest) = value.strip_prefix("wss://") {
        (true, rest)
    } else if let Some(rest) = value.strip_prefix("ws://") {
        (false, rest)
    } else {
        if !is_valid_host(value) || legacy_port == 0 {
            return Err("remote endpoint must be a ws:// or wss:// URL".to_string());
        }
        return Ok(RemoteEndpoint {
            url: format!("ws://{}:{legacy_port}", bracket_host(value)),
            host: value.to_string(),
            port: legacy_port,
            secure: false,
        });
    };
    let authority = authority.strip_suffix('/').unwrap_or(authority);
    if authority.is_empty()
        || authority.contains('/')
        || authority.contains('?')
        || authority.contains('#')
        || authority.contains('@')
    {
        return Err("remote URL cannot contain credentials, a path, query, or fragment".to_string());
    }
    let default_port = if secure { 443 } else { 80 };
    let (host, port) = if let Some(rest) = authority.strip_prefix('[') {
        let close = rest
            .find(']')
            .ok_or_else(|| "invalid bracketed IPv6 address".to_string())?;
        let host = &rest[..close];
        let suffix = &rest[close + 1..];
        let port = if suffix.is_empty() {
            default_port
        } else {
            suffix
                .strip_prefix(':')
                .ok_or_else(|| "invalid remote URL port".to_string())?
                .parse::<u16>()
                .map_err(|_| "invalid remote URL port".to_string())?
        };
        (host.to_string(), port)
    } else if let Some((candidate, raw_port)) = authority.rsplit_once(':') {
        if candidate.contains(':') {
            return Err("IPv6 addresses must be enclosed in brackets".to_string());
        }
        let port = raw_port
            .parse::<u16>()
            .map_err(|_| "invalid remote URL port".to_string())?;
        (candidate.to_string(), port)
    } else {
        (authority.to_string(), default_port)
    };
    if !is_valid_host(&host) {
        return Err("remote URL host must be an IP address or hostname".to_string());
    }
    if port == 0 {
        return Err("remote URL port must be between 1 and 65535".to_string());
    }
    let port_suffix = if port == default_port {
        String::new()
    } else {
        format!(":{port}")
    };
    Ok(RemoteEndpoint {
        url: format!(
            "{}://{}{}",
            if secure { "wss" } else { "ws" },
            bracket_host(&host),
            port_suffix,
        ),
        host,
        port,
        secure,
    })
}

fn bracket_host(host: &str) -> String {
    if host.contains(':') {
        format!("[{host}]")
    } else {
        host.to_string()
    }
}

fn resolve_addrs(host: &str, port: u16) -> Result<Vec<SocketAddr>, String> {
    if let Ok(ip) = host.parse::<IpAddr>() {
        return Ok(vec![SocketAddr::new(ip, port)]);
    }
    let addrs: Vec<SocketAddr> = (host, port)
        .to_socket_addrs()
        .map_err(|e| format!("cannot resolve host {host:?}: {e}"))?
        .collect();
    if addrs.is_empty() {
        return Err(format!("host {host:?} resolved to no addresses"));
    }
    Ok(addrs)
}

// Ceiling for one inflated message — guards against a decompression bomb from a compromised daemon.
const WS_MAX_INFLATED_BYTES: usize = 256 * 1024 * 1024;

fn ws_deflate_accepted(response_head: &str) -> bool {
    for line in response_head.lines() {
        let Some((name, value)) = line.split_once(':') else {
            continue;
        };
        if !name.trim().eq_ignore_ascii_case("sec-websocket-extensions") {
            continue;
        }
        for ext in value.split(',') {
            let ext_name = ext.split(';').next().unwrap_or("").trim();
            if ext_name.eq_ignore_ascii_case("permessage-deflate") {
                return true;
            }
        }
    }
    false
}

fn ws_header<'a>(response_head: &'a str, target: &str) -> Option<&'a str> {
    response_head.lines().skip(1).find_map(|line| {
        let (name, value) = line.split_once(':')?;
        name.trim().eq_ignore_ascii_case(target).then(|| value.trim())
    })
}

fn ws_expected_accept(key: &str) -> String {
    let mut digest = Sha1::new();
    digest.update(key.as_bytes());
    digest.update(b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11");
    base64::engine::general_purpose::STANDARD.encode(digest.finalize())
}

// RFC 7692: strip happens server-side, so the 00 00 FF FF tail is re-appended before a raw inflate; the Decompress persists per connection because context takeover shares the dictionary across messages.
fn inflate_ws_message(inflater: &mut Decompress, payload: &[u8]) -> Result<Vec<u8>, String> {
    let mut input = Vec::with_capacity(payload.len() + 4);
    input.extend_from_slice(payload);
    input.extend_from_slice(&[0x00, 0x00, 0xff, 0xff]);
    let mut out: Vec<u8> = Vec::with_capacity((payload.len().saturating_mul(4)).clamp(4096, 1 << 20));
    let mut consumed = 0_usize;
    loop {
        if out.len() == out.capacity() {
            if out.capacity() >= WS_MAX_INFLATED_BYTES {
                return Err("websocket inflate: message too large".to_string());
            }
            out.reserve(out.capacity().max(4096));
        }
        let before_in = inflater.total_in();
        let before_out = inflater.total_out();
        let status = inflater
            .decompress_vec(&input[consumed..], &mut out, FlushDecompress::Sync)
            .map_err(|e| format!("websocket inflate: {e}"))?;
        consumed += (inflater.total_in() - before_in) as usize;
        let progressed =
            inflater.total_in() > before_in || inflater.total_out() > before_out;
        if matches!(status, Status::StreamEnd) {
            inflater.reset(false);
            break;
        }
        if consumed >= input.len() && out.len() < out.capacity() {
            break;
        }
        if !progressed && out.len() < out.capacity() {
            return Err("websocket inflate: stalled stream".to_string());
        }
    }
    Ok(out)
}

enum WsStream {
    Plain(TcpStream),
    Tls(Box<rustls::StreamOwned<rustls::ClientConnection, TcpStream>>),
}

impl WsStream {
    fn tcp(&self) -> &TcpStream {
        match self {
            Self::Plain(stream) => stream,
            Self::Tls(stream) => &stream.sock,
        }
    }
}

impl Read for WsStream {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        match self {
            Self::Plain(stream) => stream.read(buf),
            Self::Tls(stream) => stream.read(buf),
        }
    }
}

impl Write for WsStream {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        match self {
            Self::Plain(stream) => stream.write(buf),
            Self::Tls(stream) => stream.write(buf),
        }
    }

    fn flush(&mut self) -> std::io::Result<()> {
        match self {
            Self::Plain(stream) => stream.flush(),
            Self::Tls(stream) => stream.flush(),
        }
    }
}

struct WsClient {
    stream: WsStream,
    inflater: Option<Decompress>,
}

impl WsClient {
    fn connect(
        remote: &str,
        legacy_port: u16,
        connect_timeout: Duration,
        read_timeout: Duration,
    ) -> Result<Self, String> {
        let endpoint = parse_remote_endpoint(remote, legacy_port)?;
        let host = endpoint.host.as_str();
        let port = endpoint.port;
        let addrs = resolve_addrs(host, port)?;
        let mut stream = None;
        let mut last_err = format!("connect {}: no address", endpoint.url);
        for addr in &addrs {
            match TcpStream::connect_timeout(addr, connect_timeout) {
                Ok(s) => {
                    stream = Some(s);
                    break;
                }
                Err(e) => last_err = format!("connect {} ({addr}): {e}", endpoint.url),
            }
        }
        let stream = stream.ok_or(last_err)?;
        // Disable Nagle: chatty JSON-RPC frames suffer 40ms/RTT penalty otherwise.
        stream.set_nodelay(true).ok();
        // TCP keepalive: catch silently-broken Tailscale tunnels in ~60s.
        let socket = socket2::SockRef::from(&stream);
        let ka = socket2::TcpKeepalive::new()
            .with_time(Duration::from_secs(WS_KEEPALIVE_IDLE_SECS))
            .with_interval(Duration::from_secs(WS_KEEPALIVE_INTERVAL_SECS));
        socket.set_tcp_keepalive(&ka).ok();
        let mut stream = if endpoint.secure {
            let roots = rustls::RootCertStore::from_iter(
                webpki_roots::TLS_SERVER_ROOTS.iter().cloned(),
            );
            let config = rustls::ClientConfig::builder()
                .with_root_certificates(roots)
                .with_no_client_auth();
            let server_name = rustls::pki_types::ServerName::try_from(endpoint.host.clone())
                .map_err(|_| "invalid TLS server name".to_string())?;
            let connection = rustls::ClientConnection::new(Arc::new(config), server_name)
                .map_err(|e| format!("tls setup: {e}"))?;
            WsStream::Tls(Box::new(rustls::StreamOwned::new(connection, stream)))
        } else {
            WsStream::Plain(stream)
        };
        stream
            .tcp()
            .set_read_timeout(Some(read_timeout))
            .map_err(|e| format!("set read timeout: {e}"))?;
        stream
            .tcp()
            .set_write_timeout(Some(read_timeout))
            .map_err(|e| format!("set write timeout: {e}"))?;
        let key = base64::engine::general_purpose::STANDARD
            .encode(uuid::Uuid::new_v4().as_bytes());
        let req = format!(
            "GET / HTTP/1.1\r\nHost: {}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Extensions: permessage-deflate; client_max_window_bits\r\n\r\n",
            if port == if endpoint.secure { 443 } else { 80 } {
                bracket_host(host)
            } else {
                format!("{}:{port}", bracket_host(host))
            }
        );
        stream
            .write_all(req.as_bytes())
            .map_err(|e| format!("websocket handshake write: {e}"))?;
        let mut response = Vec::new();
        let mut buf = [0_u8; 1];
        while !response.ends_with(b"\r\n\r\n") {
            stream
                .read_exact(&mut buf)
                .map_err(|e| format!("websocket handshake read: {e}"))?;
            response.push(buf[0]);
            if response.len() > 8192 {
                return Err("websocket handshake response too large".to_string());
            }
        }
        let head = String::from_utf8_lossy(&response);
        if !head.starts_with("HTTP/1.1 101") && !head.starts_with("HTTP/1.0 101") {
            return Err(format!(
                "websocket handshake failed: {}",
                head.lines().next().unwrap_or("")
            ));
        }
        let expected_accept = ws_expected_accept(&key);
        if ws_header(&head, "Sec-WebSocket-Accept") != Some(expected_accept.as_str()) {
            return Err("websocket handshake failed: invalid Sec-WebSocket-Accept".to_string());
        }
        let inflater = ws_deflate_accepted(&head).then(|| Decompress::new(false));
        Ok(Self { stream, inflater })
    }

    fn set_timeouts(&mut self, timeout: Duration) -> Result<(), String> {
        self.stream
            .tcp()
            .set_read_timeout(Some(timeout))
            .map_err(|e| format!("set read timeout: {e}"))?;
        self.stream
            .tcp()
            .set_write_timeout(Some(timeout))
            .map_err(|e| format!("set write timeout: {e}"))
    }

    fn request(&mut self, id: &str, value: &Value) -> Result<Value, String> {
        self.send_json(value)?;
        loop {
            let frame = self.read_text()?;
            let payload: Value =
                serde_json::from_str(&frame).map_err(|e| format!("decode: {e}"))?;
            if payload
                .get("id")
                .and_then(|x| x.as_str())
                .map(|frame_id| frame_id != id)
                .unwrap_or(true)
            {
                continue;
            }
            let response: ControlResponse =
                serde_json::from_value(payload).map_err(|e| format!("decode: {e}"))?;
            if let Some(err) = response.error {
                return Err(format_rpc_error(&err));
            }
            return response
                .result
                .ok_or_else(|| "daemon returned neither result nor error".to_string());
        }
    }

    fn send_json(&mut self, value: &Value) -> Result<(), String> {
        let text = serde_json::to_string(value).map_err(|e| format!("encode: {e}"))?;
        self.send_text(&text)
    }

    fn send_text(&mut self, text: &str) -> Result<(), String> {
        let payload = text.as_bytes();
        let mut frame = Vec::with_capacity(payload.len() + 14);
        frame.push(0x81);
        if payload.len() < 126 {
            frame.push(0x80 | payload.len() as u8);
        } else if payload.len() <= u16::MAX as usize {
            frame.push(0x80 | 126);
            frame.extend_from_slice(&(payload.len() as u16).to_be_bytes());
        } else {
            frame.push(0x80 | 127);
            frame.extend_from_slice(&(payload.len() as u64).to_be_bytes());
        }
        let mask = [0x13_u8, 0x37, 0x42, 0x99];
        frame.extend_from_slice(&mask);
        for (i, b) in payload.iter().enumerate() {
            frame.push(b ^ mask[i % 4]);
        }
        self.stream
            .write_all(&frame)
            .map_err(|e| format!("websocket write: {e}"))
    }

    fn read_text(&mut self) -> Result<String, String> {
        loop {
            let mut head = [0_u8; 2];
            self.stream
                .read_exact(&mut head)
                .map_err(|e| format!("websocket read: {e}"))?;
            let opcode = head[0] & 0x0f;
            let rsv1 = (head[0] & 0x40) != 0;
            let masked = (head[1] & 0x80) != 0;
            let mut len = (head[1] & 0x7f) as u64;
            if len == 126 {
                let mut b = [0_u8; 2];
                self.stream
                    .read_exact(&mut b)
                    .map_err(|e| format!("websocket len read: {e}"))?;
                len = u16::from_be_bytes(b) as u64;
            } else if len == 127 {
                let mut b = [0_u8; 8];
                self.stream
                    .read_exact(&mut b)
                    .map_err(|e| format!("websocket len read: {e}"))?;
                len = u64::from_be_bytes(b);
            }
            let mask = if masked {
                let mut m = [0_u8; 4];
                self.stream
                    .read_exact(&mut m)
                    .map_err(|e| format!("websocket mask read: {e}"))?;
                Some(m)
            } else {
                None
            };
            let mut payload = vec![0_u8; len as usize];
            self.stream
                .read_exact(&mut payload)
                .map_err(|e| format!("websocket payload read: {e}"))?;
            if let Some(m) = mask {
                for (i, b) in payload.iter_mut().enumerate() {
                    *b ^= m[i % 4];
                }
            }
            match opcode {
                0x1 => {
                    let bytes = if rsv1 {
                        let inflater = self.inflater.as_mut().ok_or_else(|| {
                            "websocket: compressed frame without negotiated permessage-deflate"
                                .to_string()
                        })?;
                        inflate_ws_message(inflater, &payload)?
                    } else {
                        payload
                    };
                    return String::from_utf8(bytes)
                        .map_err(|e| format!("websocket text utf8: {e}"));
                }
                0x8 => return Err("websocket closed by daemon".to_string()),
                0x9 => self.send_pong(&payload)?,
                0xa => continue,
                _ => continue,
            }
        }
    }

    fn send_pong(&mut self, payload: &[u8]) -> Result<(), String> {
        let mut frame = Vec::with_capacity(payload.len() + 6);
        frame.push(0x8a);
        frame.push(0x80 | payload.len() as u8);
        let mask = [0x44_u8, 0x45, 0x56, 0x31];
        frame.extend_from_slice(&mask);
        for (i, b) in payload.iter().enumerate() {
            frame.push(b ^ mask[i % 4]);
        }
        self.stream
            .write_all(&frame)
            .map_err(|e| format!("websocket pong write: {e}"))
    }
}

// Re-probing a healthy connection must not flip Online→Probing→Online — each transition fans out to the UI and re-triggers per-profile refetches.
fn should_mark_probing(id: &str) -> bool {
    status_map()
        .lock()
        .map(|map| !matches!(map.get(id), Some(entry) if entry.status == ConnectionStatus::Online))
        .unwrap_or(true)
}

pub fn probe_connection(conn: &HostConnection) {
    let id = conn.id().to_string();
    if should_mark_probing(&id) {
        set_status(&id, ConnectionStatus::Probing, None);
    }
    let timeout = probe_timeout_for(conn);
    let probe_once = || match conn {
        HostConnection::Local { .. } => {
            call_local_inner("host.profiles.list", json!({}), timeout)
        }
        HostConnection::Remote {
            host, port, token, ..
        } => call_remote_once(
            &id,
            host,
            *port,
            token,
            "host.profiles.list",
            json!({}),
            timeout,
        ),
    };
    let mut result = probe_once();
    if let Err(e) = &result {
        let retryable = match conn {
            HostConnection::Local { .. } => true,
            HostConnection::Remote { .. } => {
                !matches!(
                    classify_remote_error(e),
                    ConnectionStatus::AuthFailed | ConnectionStatus::Disabled
                )
            }
        };
        if retryable {
            std::thread::sleep(Duration::from_millis(PROBE_RETRY_DELAY_MS));
            result = probe_once();
        }
    }
    match result {
        Ok(_) => {
            set_status(&id, ConnectionStatus::Online, None);
            persist_last_connected(&id);
            // A successful authenticated probe proves the grant is valid — drop any stale revoke latch so the connection is usable without a re-pair.
            clear_connection_revoked(&id);
            let version_call = match conn {
                HostConnection::Local { .. } => {
                    call_local_inner("host.version", json!({}), timeout)
                }
                HostConnection::Remote {
                    host, port, token, ..
                } => call_remote_once(
                    &id,
                    host,
                    *port,
                    token,
                    "host.version",
                    json!({}),
                    timeout,
                ),
            };
            let version_value = version_call.ok();
            let version = version_value
                .as_ref()
                .and_then(|v| v.get("version"))
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());
            let update_available = version_value
                .as_ref()
                .and_then(|v| v.get("update_available"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(|s| s.to_string());
            set_update_available(&id, update_available);
            set_version(&id, version);
            let role = version_value
                .as_ref()
                .and_then(|v| v.get("role"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(|s| s.to_string());
            set_role(&id, role.clone());
            if role.is_some() {
                persist_role(&id, role);
            }
            let device_id = version_value
                .as_ref()
                .and_then(|v| v.get("device_id"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(|s| s.to_string());
            if let Some(did) = device_id {
                persist_device_id(&id, &did);
            }
            if let HostConnection::Remote { host, port, token, .. } = conn {
                let device_name = std::env::var("HOSTNAME").unwrap_or_else(|_| "Desktop".into());
                let _ = call_remote_once(
                    &id,
                    host,
                    *port,
                    token,
                    "host.connections.register_device",
                    json!({
                        "client": "desktop",
                        "name": device_name,
                        "app_version": env!("CARGO_PKG_VERSION"),
                    }),
                    timeout,
                );
            }
        }
        Err(e) => {
            let next = match conn {
                HostConnection::Local { .. } => ConnectionStatus::Offline,
                HostConnection::Remote { .. } => {
                    let cls = classify_remote_error(&e);
                    if is_revocation_error(&e) {
                        mark_connection_revoked(&id);
                    }
                    cls
                }
            };
            record_probe_failure(&id, next, e);
        }
    }
}

pub fn probe_active() {
    use std::sync::atomic::{AtomicBool, Ordering};
    static RUNNING: AtomicBool = AtomicBool::new(false);
    if RUNNING.compare_exchange(false, true, Ordering::AcqRel, Ordering::Relaxed).is_err() {
        return;
    }
    let state = load_connections();
    if let Some(conn) = state.connections.iter().find(|c| c.id() == state.active_id) {
        probe_connection(conn);
    }
    RUNNING.store(false, Ordering::Release);
}

pub fn probe_all() {
    use std::sync::atomic::{AtomicBool, Ordering};
    static RUNNING: AtomicBool = AtomicBool::new(false);
    if RUNNING.compare_exchange(false, true, Ordering::AcqRel, Ordering::Relaxed).is_err() {
        return;
    }
    let state = load_connections();
    for conn in state.connections {
        probe_connection(&conn);
    }
    RUNNING.store(false, Ordering::Release);
}

fn roles_backfill_targets(state: &ConnectionsState) -> Vec<&HostConnection> {
    state
        .connections
        .iter()
        .filter(|c| c.id() != state.active_id && c.last_role().is_none())
        .collect()
}

fn backfill_role(conn: &HostConnection) {
    let id = conn.id().to_string();
    let timeout = probe_timeout_for(conn);
    let version_call = match conn {
        HostConnection::Local { .. } => call_local_inner("host.version", json!({}), timeout),
        HostConnection::Remote { host, port, token, .. } => {
            call_remote_once(&id, host, *port, token, "host.version", json!({}), timeout)
        }
    };
    let role = match version_call {
        Ok(v) => v
            .get("role")
            .and_then(|r| r.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string()),
        Err(_) => None,
    };
    if role.is_some() {
        set_role(&id, role.clone());
        persist_role(&id, role);
    }
}

// Learn the role of never-probed connections with a bounded host.version fan-out — NOT the full serial probe_all, the active one (already probed) is skipped, and probe_all's RUNNING flag is left untouched.
pub fn backfill_missing_roles() {
    const MAX_CONCURRENT: usize = 4;
    let state = load_connections();
    let targets: Vec<HostConnection> =
        roles_backfill_targets(&state).into_iter().cloned().collect();
    for chunk in targets.chunks(MAX_CONCURRENT) {
        let handles: Vec<_> = chunk
            .iter()
            .cloned()
            .map(|conn| std::thread::spawn(move || backfill_role(&conn)))
            .collect();
        for h in handles {
            let _ = h.join();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn long_operations_override_default_rpc_windows() {
        let local = HostConnection::Local {
            id: LOCAL_ID.to_string(),
            name: "Local daemon".to_string(),
            device_id: None,
            last_connected: None,
            last_role: None,
        };
        let remote = HostConnection::Remote {
            id: "remote-1".to_string(),
            name: "Remote".to_string(),
            host: "100.0.0.1".to_string(),
            port: 7423,
            token: "t".to_string(),
            revoked: false,
            device_id: None,
            last_connected: None,
            last_role: None,
        };
        assert_eq!(read_timeout_for(&local, None), Duration::from_secs(READ_TIMEOUT_LOCAL_SECS));
        assert_eq!(read_timeout_for(&remote, None), Duration::from_secs(READ_TIMEOUT_REMOTE_SECS));
        let fetch = Duration::from_secs(READ_TIMEOUT_FETCH_SECS);
        assert_eq!(read_timeout_for(&local, Some(fetch)), Duration::from_secs(60));
        assert_eq!(read_timeout_for(&remote, Some(fetch)), Duration::from_secs(60));
        let update = Duration::from_secs(READ_TIMEOUT_UPDATE_SECS);
        assert_eq!(read_timeout_for(&local, Some(update)), Duration::from_secs(360));
        assert_eq!(read_timeout_for(&remote, Some(update)), Duration::from_secs(360));
        assert_eq!(read_timeout_for(&remote, None), Duration::from_secs(20));
    }

    #[test]
    fn probe_timeout_is_shorter_for_local_connections() {
        let local = HostConnection::Local {
            id: LOCAL_ID.to_string(),
            name: "Local daemon".to_string(),
            device_id: None,
            last_connected: None,
            last_role: None,
        };
        let remote = HostConnection::Remote {
            id: "remote-1".to_string(),
            name: "Remote".to_string(),
            host: "10.0.0.2".to_string(),
            port: 49200,
            token: "secret".to_string(),
            revoked: false,
            device_id: None,
            last_connected: None,
            last_role: None,
        };
        assert_eq!(
            probe_timeout_for(&local),
            Duration::from_millis(PROBE_LOCAL_TIMEOUT_MS)
        );
        assert_eq!(
            probe_timeout_for(&remote),
            Duration::from_millis(PROBE_REMOTE_TIMEOUT_MS)
        );
    }

    #[test]
    fn ordered_for_display_pins_active_then_local_ignoring_last_connected() {
        let conns = vec![
            HostConnection::Local {
                id: LOCAL_ID.to_string(),
                name: "Local daemon".to_string(),
                device_id: None,
                last_connected: Some(100),
                last_role: None,
            },
            HostConnection::Remote {
                id: "casa".to_string(),
                name: "casa".to_string(),
                host: "10.0.0.2".to_string(),
                port: 49200,
                token: "t".to_string(),
                revoked: false,
                device_id: None,
                last_connected: Some(1),
                last_role: None,
            },
            HostConnection::Remote {
                id: "mirai".to_string(),
                name: "mirai".to_string(),
                host: "10.0.0.3".to_string(),
                port: 49201,
                token: "t".to_string(),
                revoked: false,
                device_id: None,
                last_connected: Some(999),
                last_role: None,
            },
        ];
        let ids: Vec<&str> = ordered_for_display(&conns, "casa")
            .iter()
            .map(|c| c.id())
            .collect();
        assert_eq!(ids, vec!["casa", LOCAL_ID, "mirai"]);
    }

    #[test]
    fn device_id_round_trip_through_set_and_get() {
        let mut local = HostConnection::Local {
            id: LOCAL_ID.to_string(),
            name: "Local".to_string(),
            device_id: None,
            last_connected: None,
            last_role: None,
        };
        assert!(local.device_id().is_none());
        local.set_device_id(Some("uuid-mac".to_string()));
        assert_eq!(local.device_id(), Some("uuid-mac"));

        let mut remote = HostConnection::Remote {
            id: "r".to_string(),
            name: "R".to_string(),
            host: "1.1.1.1".to_string(),
            port: 49200,
            token: "t".to_string(),
            revoked: false,
            device_id: Some("uuid-mac".to_string()),
            last_connected: None,
            last_role: None,
        };
        assert_eq!(remote.device_id(), Some("uuid-mac"));
        remote.set_device_id(None);
        assert!(remote.device_id().is_none());
    }

    #[test]
    fn effective_role_prefers_live_then_persisted() {
        let conn = HostConnection::Remote {
            id: "role-precedence-1".to_string(),
            name: "x".to_string(),
            host: "1.1.1.1".to_string(),
            port: 49200,
            token: "t".to_string(),
            revoked: false,
            device_id: None,
            last_connected: None,
            last_role: Some("member".to_string()),
        };
        assert_eq!(effective_role(&conn).as_deref(), Some("member"));
        set_role("role-precedence-1", Some("admin".to_string()));
        assert_eq!(effective_role(&conn).as_deref(), Some("admin"));
    }

    #[test]
    fn last_role_survives_json_round_trip_and_legacy_defaults_none() {
        let conn = HostConnection::Remote {
            id: "r".to_string(),
            name: "R".to_string(),
            host: "1.1.1.1".to_string(),
            port: 49200,
            token: "t".to_string(),
            revoked: false,
            device_id: None,
            last_connected: None,
            last_role: Some("member".to_string()),
        };
        let text = serde_json::to_string(&conn).unwrap();
        let back: HostConnection = serde_json::from_str(&text).unwrap();
        assert_eq!(back.last_role(), Some("member"));

        let legacy = decode_connections(
            r#"{"active_id":"r","connections":[{"kind":"remote","id":"r","name":"R","host":"1.1.1.1","port":49200,"token":"t"}]}"#,
        )
        .unwrap();
        assert_eq!(legacy.connections[0].last_role(), None);
    }

    #[test]
    fn remote_endpoint_parses_and_canonicalizes_ws_and_wss() {
        assert_eq!(
            parse_remote_endpoint("wss://client.example.com:443/", 0).unwrap(),
            RemoteEndpoint {
                url: "wss://client.example.com".to_string(),
                host: "client.example.com".to_string(),
                port: 443,
                secure: true,
            },
        );
        assert_eq!(
            parse_remote_endpoint("ws://100.64.10.2:49200", 0).unwrap().port,
            49200,
        );
        assert_eq!(
            parse_remote_endpoint("100.64.10.2", 49200).unwrap().url,
            "ws://100.64.10.2:49200",
        );
    }

    #[test]
    fn remote_endpoint_rejects_non_websocket_or_ambiguous_urls() {
        for value in [
            "https://client.example.com",
            "wss://user:secret@client.example.com",
            "wss://client.example.com/rpc",
            "ws://client.example.com:0",
        ] {
            assert!(parse_remote_endpoint(value, 0).is_err(), "accepted {value}");
        }
    }

    #[test]
    fn a_revoked_active_connection_falls_back_to_local() {
        let _fs = TEST_FS_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let dir = std::env::temp_dir().join(format!(
            "alpi-revoked-active-test-{}",
            std::process::id(),
        ));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        *config_dir_override().lock().unwrap() = Some(dir.clone());

        let state = ConnectionsState {
            active_id: "revoked".to_string(),
            connections: vec![HostConnection::Remote {
                id: "revoked".to_string(),
                name: "Revoked".to_string(),
                host: "wss://client.example.com".to_string(),
                port: 0,
                token: "secret".to_string(),
                revoked: true,
                device_id: None,
                last_connected: None,
                last_role: None,
            }],
        };
        save_connections(&state).unwrap();

        let loaded = load_connections();
        assert_eq!(loaded.active_id, LOCAL_ID);
        assert!(set_active_connection("revoked".to_string()).is_err());

        *config_dir_override().lock().unwrap() = None;
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn is_revocation_error_excludes_transient_and_disabled() {
        assert!(is_revocation_error("alp -32000: auth-failed"));
        assert!(!is_revocation_error(
            "alp -32000: auth-failed — socket-identity-changed"
        ));
        assert!(!is_revocation_error(
            "alp -32000: auth-failed — connection-disabled"
        ));
        assert!(!is_revocation_error("connect ws://10.0.0.2:49200: refused"));
    }

    #[test]
    fn clear_connection_revoked_drops_the_latch() {
        let _fs = TEST_FS_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let dir = std::env::temp_dir().join(format!("alpi-unrevoke-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        *config_dir_override().lock().unwrap() = Some(dir.clone());

        let state = ConnectionsState {
            active_id: LOCAL_ID.to_string(),
            connections: vec![HostConnection::Remote {
                id: "r".to_string(),
                name: "R".to_string(),
                host: "wss://client.example.com".to_string(),
                port: 0,
                token: "secret".to_string(),
                revoked: true,
                device_id: None,
                last_connected: None,
                last_role: None,
            }],
        };
        save_connections(&state).unwrap();

        clear_connection_revoked("r");

        let loaded = load_connections();
        let still_revoked = loaded
            .connections
            .iter()
            .any(|c| matches!(c, HostConnection::Remote { revoked: true, .. }));
        assert!(!still_revoked, "a healed probe must drop the revoke latch");
        assert!(
            set_active_connection("r".to_string()).is_ok(),
            "an un-revoked connection can be activated again"
        );

        *config_dir_override().lock().unwrap() = None;
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn remote_connection_json_reads_legacy_host_and_writes_url() {
        let state = decode_connections(
            r#"{"active_id":"r","connections":[{"kind":"remote","id":"r","name":"R","host":"100.64.0.1","port":49200,"token":"t"}]}"#,
        )
        .unwrap();
        let value = serde_json::to_value(&state.connections[0]).unwrap();
        assert_eq!(value["url"], json!("100.64.0.1"));
        assert!(value.get("host").is_none());
    }

    #[test]
    fn connections_file_keeps_legacy_host_and_port_for_desktop_rollback() {
        let _fs = TEST_FS_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let dir = std::env::temp_dir().join(format!(
            "alpi-conns-rollback-test-{}",
            std::process::id(),
        ));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        *config_dir_override().lock().unwrap() = Some(dir.clone());

        let state = ConnectionsState {
            active_id: "secure".to_string(),
            connections: vec![HostConnection::Remote {
                id: "secure".to_string(),
                name: "Secure".to_string(),
                host: "wss://client.example.com".to_string(),
                port: 0,
                token: "secret".to_string(),
                revoked: false,
                device_id: None,
                last_connected: None,
                last_role: None,
            }],
        };
        save_connections(&state).unwrap();

        let text = std::fs::read_to_string(dir.join("connections.json")).unwrap();
        let value: Value = serde_json::from_str(&text).unwrap();
        let row = &value["connections"][0];
        assert_eq!(row["url"], json!("wss://client.example.com"));
        assert_eq!(row["host"], json!("client.example.com"));
        assert_eq!(row["port"], json!(443));

        let loaded = load_connections();
        match &loaded.connections[1] {
            HostConnection::Remote { host, port, .. } => {
                assert_eq!(host, "wss://client.example.com");
                assert_eq!(*port, 443);
            }
            HostConnection::Local { .. } => panic!("expected remote connection"),
        }

        *config_dir_override().lock().unwrap() = None;
        let _ = std::fs::remove_dir_all(&dir);
    }

    fn remote_with_role(id: &str, last_role: Option<&str>) -> HostConnection {
        HostConnection::Remote {
            id: id.to_string(),
            name: id.to_string(),
            host: "127.0.0.1".to_string(),
            port: 49200,
            token: "t".to_string(),
            revoked: false,
            device_id: None,
            last_connected: None,
            last_role: last_role.map(|s| s.to_string()),
        }
    }

    #[test]
    fn roles_backfill_targets_selects_only_unknown_roles_and_excludes_active() {
        let state = ConnectionsState {
            active_id: "active".to_string(),
            connections: vec![
                remote_with_role("active", None),
                remote_with_role("known", Some("member")),
                remote_with_role("unknown-1", None),
                remote_with_role("unknown-2", None),
            ],
        };
        let ids: Vec<&str> = roles_backfill_targets(&state).iter().map(|c| c.id()).collect();
        assert_eq!(ids, vec!["unknown-1", "unknown-2"]);
    }

    static TEST_FS_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn concurrent_metadata_write_does_not_resurrect_a_deleted_connection() {
        let _fs = TEST_FS_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let dir = std::env::temp_dir().join(format!("alpi-conns-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        *config_dir_override().lock().unwrap() = Some(dir.clone());

        let seed = ConnectionsState {
            active_id: LOCAL_ID.to_string(),
            connections: vec![
                HostConnection::Local {
                    id: LOCAL_ID.to_string(),
                    name: "L".to_string(),
                    device_id: None,
                    last_connected: None,
                    last_role: None,
                },
                remote_with_role("remote-a", None),
                remote_with_role("remote-b", None),
            ],
        };
        save_connections(&seed).unwrap();

        let hammer = std::thread::spawn(|| {
            for _ in 0..300 {
                persist_last_connected("remote-a");
            }
        });
        let forget = std::thread::spawn(|| {
            std::thread::sleep(Duration::from_millis(2));
            let _ = forget_connection("remote-b".to_string());
        });
        hammer.join().unwrap();
        forget.join().unwrap();

        let text = std::fs::read_to_string(dir.join("connections.json")).unwrap();
        let parsed = decode_connections(&text).expect("valid connections on disk");
        let ids: Vec<&str> = parsed.connections.iter().map(|c| c.id()).collect();
        assert!(ids.contains(&"remote-a"), "remote-a must survive: {ids:?}");
        assert!(
            !ids.contains(&"remote-b"),
            "a stale-snapshot metadata write must not resurrect forgotten remote-b: {ids:?}",
        );

        *config_dir_override().lock().unwrap() = None;
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn classify_remote_errors() {
        assert_eq!(
            classify_remote_error("alp -32000: auth-failed — connection-disabled"),
            ConnectionStatus::Disabled
        );
        assert_eq!(
            classify_remote_error("alp -32000: auth-failed"),
            ConnectionStatus::AuthFailed
        );
        assert_eq!(
            classify_remote_error("alp -32004: not-found"),
            ConnectionStatus::Online
        );
        assert_eq!(
            classify_remote_error("connect ws://10.0.0.2:49200: refused"),
            ConnectionStatus::Offline
        );
    }

    #[test]
    fn formats_structured_auth_reason_for_status_classification() {
        let error = ControlError {
            code: -32000,
            message: "auth-failed".to_string(),
            data: Some(json!({"reason": "connection-disabled"})),
        };

        assert_eq!(
            format_rpc_error(&error),
            "alp -32000: auth-failed — connection-disabled"
        );
    }

    #[test]
    fn classify_local_rpc_errors_as_online() {
        assert_eq!(
            classify_local_error("alp -32004: not-found"),
            ConnectionStatus::Online
        );
        assert_eq!(
            classify_local_error("connect /tmp/host.sock: refused"),
            ConnectionStatus::Offline
        );
    }

    #[test]
    fn resolve_addrs_accepts_ip_and_resolvable_host() {
        assert_eq!(resolve_addrs("100.64.0.1", 49200).unwrap().len(), 1);
        assert!(!resolve_addrs("localhost", 49200).unwrap().is_empty());
        assert!(resolve_addrs("no.such.host.invalid", 49200).is_err());
    }

    #[test]
    fn is_valid_host_accepts_ips_and_hostnames() {
        for h in ["100.64.0.1", "::1", "casa", "casa.local", "host.tail1234.ts.net"] {
            assert!(is_valid_host(h), "expected {h:?} to be valid");
        }
        for h in ["", "a b", "http://casa", "casa/x", "-bad", "bad-", "casa..local"] {
            assert!(!is_valid_host(h), "expected {h:?} to be invalid");
        }
    }

    #[test]
    fn ordered_for_display_is_stable_and_ignores_recency() {
        let remote = |id: &str, ts: Option<i64>| HostConnection::Remote {
            id: id.to_string(),
            name: id.to_string(),
            host: "1.1.1.1".to_string(),
            port: 49200,
            token: "t".to_string(),
            revoked: false,
            device_id: None,
            last_connected: ts,
            last_role: None,
        };
        let conns = vec![
            remote("r-old", Some(100)),
            HostConnection::Local {
                id: LOCAL_ID.to_string(),
                name: "Local".to_string(),
                device_id: None,
                last_connected: None,
                last_role: None,
            },
            remote("r-new", Some(500)),
            remote("r-never", None),
        ];
        let ids: Vec<&str> = ordered_for_display(&conns, LOCAL_ID)
            .iter()
            .map(|c| c.id())
            .collect();
        assert_eq!(ids, vec![LOCAL_ID, "r-old", "r-new", "r-never"]);
    }

    #[test]
    fn sticky_offline_holds_until_threshold() {
        let id = "sticky-1";
        // Start from a clean entry, push it Online.
        set_status(id, ConnectionStatus::Online, None);
        assert_eq!(status_for(id).0, ConnectionStatus::Online);

        // First Offline observation must be absorbed (counter=1, below threshold).
        set_status(id, ConnectionStatus::Offline, Some("transient".into()));
        assert_eq!(
            status_for(id).0,
            ConnectionStatus::Online,
            "single Offline observation must not flip a previously-Online entry",
        );

        // Second Offline crosses the threshold and flips publicly.
        set_status(id, ConnectionStatus::Offline, Some("real".into()));
        assert_eq!(status_for(id).0, ConnectionStatus::Offline);
    }

    #[test]
    fn a_live_stream_outranks_a_slow_probe() {
        let id = "stream-live-1";
        set_status(id, ConnectionStatus::Online, None);
        note_stream_frame(id);

        record_probe_failure(id, ConnectionStatus::Offline, "probe timeout".into());
        record_probe_failure(id, ConnectionStatus::Offline, "probe timeout".into());
        assert_eq!(
            status_for(id).0,
            ConnectionStatus::Online,
            "frames are still arriving, so a slow probe measures load, not death",
        );

        if let Ok(map) = status_map().lock() {
            assert_eq!(map.get(id).unwrap().consecutive_failures, 0);
        }
    }

    #[test]
    fn a_live_stream_outranks_parallel_request_timeouts() {
        let id = "stream-live-request";
        set_status(id, ConnectionStatus::Online, None);
        note_stream_frame(id);

        record_request_failure(id, ConnectionStatus::Offline, "profiles timeout".into());
        record_request_failure(id, ConnectionStatus::Offline, "workgroups timeout".into());

        assert_eq!(
            status_for(id).0,
            ConnectionStatus::Online,
            "ordinary requests cannot declare a live event stream offline",
        );
    }

    #[test]
    fn a_stale_stream_lets_the_probe_through() {
        let id = "stream-stale-1";
        set_status(id, ConnectionStatus::Online, None);
        if let Ok(mut map) = status_map().lock() {
            let entry = map.get_mut(id).unwrap();
            entry.last_stream_frame = Instant::now()
                .checked_sub(Duration::from_secs(STREAM_LIVENESS_WINDOW_SECS + 5));
        }

        record_probe_failure(id, ConnectionStatus::Offline, "first".into());
        assert_eq!(status_for(id).0, ConnectionStatus::Online);
        record_probe_failure(id, ConnectionStatus::Offline, "second".into());
        assert_eq!(
            status_for(id).0,
            ConnectionStatus::Offline,
            "with no recent frames the probe is the only evidence and must win",
        );
    }

    #[test]
    fn a_recent_stream_does_not_mask_transport_failures() {
        let id = "stream-transport-failure";
        set_status(id, ConnectionStatus::Online, None);
        note_stream_frame(id);

        set_status(id, ConnectionStatus::Offline, Some("stream closed".into()));
        assert_eq!(status_for(id).0, ConnectionStatus::Online);
        set_status(id, ConnectionStatus::Offline, Some("reconnect failed".into()));
        assert_eq!(status_for(id).0, ConnectionStatus::Offline);
    }

    #[test]
    fn a_stream_frame_resets_probe_failures_and_recovers_online() {
        let id = "stream-recovers";
        set_status(id, ConnectionStatus::Online, None);
        if let Ok(mut map) = status_map().lock() {
            map.get_mut(id).unwrap().last_stream_frame = None;
        }
        record_probe_failure(id, ConnectionStatus::Offline, "first".into());

        note_stream_frame(id);
        if let Ok(mut map) = status_map().lock() {
            let entry = map.get_mut(id).unwrap();
            assert_eq!(entry.consecutive_failures, 0);
            entry.last_stream_frame = None;
        }
        record_probe_failure(id, ConnectionStatus::Offline, "second".into());
        assert_eq!(status_for(id).0, ConnectionStatus::Online);

        set_status(id, ConnectionStatus::Offline, Some("stream closed".into()));
        assert_eq!(status_for(id).0, ConnectionStatus::Offline);
        note_stream_frame(id);
        assert_eq!(status_for(id).0, ConnectionStatus::Online);
    }

    #[test]
    fn an_ignored_probe_preserves_version_metadata() {
        let id = "stream-version";
        set_status(id, ConnectionStatus::Online, None);
        set_version(id, Some("0.11.0".into()));
        note_stream_frame(id);

        record_probe_failure(id, ConnectionStatus::Offline, "timeout".into());

        assert_eq!(version_for(id), Some("0.11.0".into()));
    }

    #[test]
    fn stream_frames_do_not_clear_terminal_connection_states() {
        let auth_id = "stream-auth-failed";
        set_status(auth_id, ConnectionStatus::AuthFailed, Some("revoked".into()));
        note_stream_frame(auth_id);
        assert_eq!(status_for(auth_id).0, ConnectionStatus::AuthFailed);

        let disabled_id = "stream-disabled";
        set_status(
            disabled_id,
            ConnectionStatus::Disabled,
            Some("disabled".into()),
        );
        note_stream_frame(disabled_id);
        assert_eq!(status_for(disabled_id).0, ConnectionStatus::Disabled);
    }

    #[test]
    fn sticky_offline_resets_on_recovery() {
        let id = "sticky-2";
        set_status(id, ConnectionStatus::Online, None);
        // Burn one failure (still Online publicly).
        set_status(id, ConnectionStatus::Offline, Some("blip".into()));
        // Recovery clears the counter.
        set_status(id, ConnectionStatus::Online, None);
        // A subsequent failure must again be absorbed, not flip.
        set_status(id, ConnectionStatus::Offline, Some("blip 2".into()));
        assert_eq!(status_for(id).0, ConnectionStatus::Online);
    }

    #[test]
    fn auth_failed_is_not_subject_to_sticky_threshold() {
        let id = "sticky-3";
        set_status(id, ConnectionStatus::Online, None);
        set_status(id, ConnectionStatus::AuthFailed, Some("revoked".into()));
        assert_eq!(status_for(id).0, ConnectionStatus::AuthFailed);
    }

    #[test]
    fn disabled_is_not_subject_to_sticky_threshold() {
        let id = "sticky-disabled";
        set_status(id, ConnectionStatus::Online, None);
        set_status(id, ConnectionStatus::Disabled, Some("disabled".into()));
        assert_eq!(status_for(id).0, ConnectionStatus::Disabled);
    }

    #[test]
    fn should_retry_remote_ws_distinguishes_transport_from_app_errors() {
        // Transport-level: retry, the WS is dead.
        assert!(should_retry_remote_ws("websocket closed by daemon"));
        assert!(should_retry_remote_ws("websocket read: timed out"));
        assert!(should_retry_remote_ws("connect ws://1.2.3.4:80: refused"));
        assert!(should_retry_remote_ws("set read timeout: bad"));
        assert!(should_retry_remote_ws("set write timeout: bad"));
        // App-level RPC error: WS still alive, no retry.
        assert!(!should_retry_remote_ws("alp -32004: not-found"));
        // Auth failure: token bad, retrying won't help.
        assert!(!should_retry_remote_ws("alp -32000: auth-failed"));
        assert!(!should_retry_remote_ws(
            "alp -32000: auth-failed — connection-disabled"
        ));
    }

    #[test]
    fn retry_remote_recovers_on_second_attempt_after_transport_error() {
        let mut calls = 0;
        let r = retry_remote(|| {
            calls += 1;
            if calls == 1 {
                Err("websocket closed by daemon".to_string())
            } else {
                Ok(json!({"ok": true}))
            }
        });
        assert_eq!(calls, 2);
        assert_eq!(r.unwrap()["ok"], json!(true));
    }

    #[test]
    fn retry_remote_does_not_retry_app_errors() {
        let mut calls = 0;
        let r = retry_remote(|| {
            calls += 1;
            Err("alp -32004: not-found".to_string())
        });
        assert_eq!(calls, 1);
        assert!(r.is_err());
    }

    fn deflate_ws_test_message(compressor: &mut flate2::Compress, data: &[u8]) -> Vec<u8> {
        let before_in = compressor.total_in();
        let mut out = Vec::with_capacity(data.len() * 2 + 1024);
        compressor
            .compress_vec(data, &mut out, flate2::FlushCompress::Sync)
            .unwrap();
        assert_eq!(compressor.total_in() - before_in, data.len() as u64);
        assert!(out.ends_with(&[0x00, 0x00, 0xff, 0xff]));
        out.truncate(out.len() - 4);
        out
    }

    #[test]
    fn ws_deflate_accepted_parses_extension_headers() {
        assert!(ws_deflate_accepted(
            "HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Extensions: permessage-deflate\r\n\r\n"
        ));
        assert!(ws_deflate_accepted(
            "HTTP/1.1 101 X\r\nsec-websocket-extensions: Permessage-Deflate; server_max_window_bits=12\r\n\r\n"
        ));
        assert!(ws_deflate_accepted(
            "HTTP/1.1 101 X\r\nSec-WebSocket-Extensions: foo, permessage-deflate; client_no_context_takeover\r\n\r\n"
        ));
        assert!(!ws_deflate_accepted("HTTP/1.1 101 Switching Protocols\r\n\r\n"));
        assert!(!ws_deflate_accepted(
            "HTTP/1.1 101 X\r\nSec-WebSocket-Extensions: x-permessage-deflate-like\r\n\r\n"
        ));
        assert!(!ws_deflate_accepted(
            "HTTP/1.1 101 X\r\nX-Other: permessage-deflate\r\n\r\n"
        ));
    }

    #[test]
    fn websocket_accept_matches_rfc6455_and_header_is_case_insensitive() {
        assert_eq!(
            ws_expected_accept("dGhlIHNhbXBsZSBub25jZQ=="),
            "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        );
        let head = "HTTP/1.1 101 Switching Protocols\r\nsec-websocket-accept: value\r\n\r\n";
        assert_eq!(ws_header(head, "Sec-WebSocket-Accept"), Some("value"));
    }

    #[test]
    fn inflate_ws_message_roundtrips_a_sync_flushed_message() {
        let mut compressor = flate2::Compress::new(flate2::Compression::default(), false);
        let mut inflater = Decompress::new(false);
        let data = br#"{"id":"r1","result":{"session":{"turns":[1,2,3]}}}"#;
        let wire = deflate_ws_test_message(&mut compressor, data);
        let out = inflate_ws_message(&mut inflater, &wire).unwrap();
        assert_eq!(out, data);
    }

    #[test]
    fn inflate_ws_message_keeps_context_across_messages() {
        // Context takeover: msg2 (identical to msg1) compresses to back-references into msg1's window, so a fresh inflater must fail on it.
        let mut compressor = flate2::Compress::new(flate2::Compression::default(), false);
        let msg: Vec<u8> = (0..1024_u32).flat_map(|i| i.to_be_bytes()).collect();
        let wire1 = deflate_ws_test_message(&mut compressor, &msg);
        let wire2 = deflate_ws_test_message(&mut compressor, &msg);
        assert!(wire2.len() < wire1.len() / 2);

        let mut inflater = Decompress::new(false);
        assert_eq!(inflate_ws_message(&mut inflater, &wire1).unwrap(), msg);
        assert_eq!(inflate_ws_message(&mut inflater, &wire2).unwrap(), msg);

        // Backend-dependent: strict inflaters error on the out-of-window distance, miniz_oxide zero-fills — either way the decode must not be correct.
        let mut fresh = Decompress::new(false);
        let res = inflate_ws_message(&mut fresh, &wire2);
        assert!(res.map(|out| out != msg).unwrap_or(true));
    }

    #[test]
    fn inflate_ws_message_grows_output_beyond_initial_capacity() {
        let mut compressor = flate2::Compress::new(flate2::Compression::default(), false);
        let mut inflater = Decompress::new(false);
        let data = r#"{"user":"hola","assistant":"que tal"}"#.repeat(80_000);
        let wire = deflate_ws_test_message(&mut compressor, data.as_bytes());
        assert!(wire.len() < data.len() / 10);
        let out = inflate_ws_message(&mut inflater, &wire).unwrap();
        assert_eq!(out, data.as_bytes());
    }

    #[test]
    fn inflate_ws_message_rejects_garbage() {
        let mut inflater = Decompress::new(false);
        assert!(inflate_ws_message(&mut inflater, &[0xff, 0xff, 0xff, 0xff, 0xff]).is_err());
    }

    #[test]
    #[ignore = "live integration: set ALPI_WS_TEST_ADDR=host:port to a websockets server with compression=deflate"]
    fn ws_deflate_live_negotiation_and_inflate() {
        let addr = std::env::var("ALPI_WS_TEST_ADDR").expect("ALPI_WS_TEST_ADDR");
        let (host, port) = addr.rsplit_once(':').expect("host:port");
        let port: u16 = port.parse().expect("port");
        let mut ws = WsClient::connect(
            host,
            port,
            Duration::from_secs(4),
            Duration::from_secs(10),
        )
        .unwrap();
        assert!(ws.inflater.is_some(), "server did not negotiate permessage-deflate");
        for id in ["t1", "t2"] {
            let req = json!({"id": id, "method": "test.echo", "params": {"marker": id}});
            let result = ws.request(id, &req).unwrap();
            assert_eq!(result["echo"]["params"]["marker"], json!(id));
            assert!(result["big"].as_str().unwrap().len() >= 200_000);
        }
    }

    #[test]
    fn retry_remote_gives_up_after_one_retry() {
        let mut calls = 0;
        let r = retry_remote(|| {
            calls += 1;
            Err("websocket closed by daemon".to_string())
        });
        assert_eq!(calls, 2);
        assert!(r.is_err());
    }

    #[test]
    fn probing_is_skipped_for_online_connections_only() {
        let id = "probe-flip-online";
        assert!(should_mark_probing(id), "unknown connections still show probing");
        set_status(id, ConnectionStatus::Online, None);
        assert!(!should_mark_probing(id), "a healthy connection must not flip to probing");
        set_status(id, ConnectionStatus::AuthFailed, Some("bad token".into()));
        assert!(should_mark_probing(id), "non-online states re-enter the probing flow");
    }

    #[test]
    fn remote_gate_caps_inflight_at_four_per_connection() {
        let id = "gate-cap-1";
        let p1 = acquire_remote_slot(id);
        let _p2 = acquire_remote_slot(id);
        let _p3 = acquire_remote_slot(id);
        let _p4 = acquire_remote_slot(id);
        assert_eq!(*remote_gate(id).inflight.lock().unwrap(), 4);

        let (tx, rx) = std::sync::mpsc::channel();
        let waiter_id = id.to_string();
        let h = std::thread::spawn(move || {
            let _p5 = acquire_remote_slot(&waiter_id);
            tx.send(()).unwrap();
            std::thread::sleep(Duration::from_millis(30));
        });
        assert!(
            rx.recv_timeout(Duration::from_millis(150)).is_err(),
            "the 5th concurrent call must block while the connection is at its cap",
        );
        drop(p1);
        assert!(
            rx.recv_timeout(Duration::from_millis(500)).is_ok(),
            "freeing a slot must admit the waiting call",
        );
        h.join().unwrap();
    }

    #[test]
    fn remote_gates_are_independent_per_connection() {
        let a = "gate-indep-a";
        let _a1 = acquire_remote_slot(a);
        let _a2 = acquire_remote_slot(a);
        let _a3 = acquire_remote_slot(a);
        let _a4 = acquire_remote_slot(a);

        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            let _b = acquire_remote_slot("gate-indep-b");
            tx.send(()).unwrap();
        });
        assert!(
            rx.recv_timeout(Duration::from_millis(300)).is_ok(),
            "a saturated connection must not block calls on a different connection",
        );
    }

    #[test]
    fn remote_gate_releases_slot_on_drop() {
        let id = "gate-drop-1";
        {
            let _p = acquire_remote_slot(id);
            assert_eq!(*remote_gate(id).inflight.lock().unwrap(), 1);
        }
        assert_eq!(*remote_gate(id).inflight.lock().unwrap(), 0);
    }

    fn ep(token: &str) -> PoolEndpoint {
        ("10.0.0.2".to_string(), 49200, token.to_string())
    }

    #[test]
    fn ws_pool_roundtrips_a_connection_for_the_same_endpoint() {
        let mut pool = WsPool::<u32>::new(4, Duration::from_secs(12));
        let now = Instant::now();
        assert!(pool.checkout("casa", &ep("t"), now).is_none());
        pool.checkin("casa", ep("t"), 7, now);
        assert_eq!(pool.checkout("casa", &ep("t"), now), Some(7));
        assert!(pool.checkout("casa", &ep("t"), now).is_none());
    }

    #[test]
    fn ws_pool_discards_entries_older_than_the_idle_ttl() {
        let mut pool = WsPool::<u32>::new(4, Duration::from_secs(12));
        let created = Instant::now();
        pool.checkin("casa", ep("t"), 7, created);
        let later = created + Duration::from_secs(13);
        assert!(pool.checkout("casa", &ep("t"), later).is_none());
    }

    #[test]
    fn ws_pool_discards_entries_whose_endpoint_changed() {
        let mut pool = WsPool::<u32>::new(4, Duration::from_secs(12));
        let now = Instant::now();
        pool.checkin("casa", ep("old-token"), 7, now);
        assert!(pool.checkout("casa", &ep("new-token"), now).is_none());
        assert!(
            pool.checkout("casa", &ep("old-token"), now).is_none(),
            "mismatched entries must be dropped, not kept behind the new ones",
        );
    }

    #[test]
    fn ws_pool_caps_idle_connections_per_key() {
        let mut pool = WsPool::<u32>::new(2, Duration::from_secs(12));
        let now = Instant::now();
        pool.checkin("casa", ep("t"), 1, now);
        pool.checkin("casa", ep("t"), 2, now);
        pool.checkin("casa", ep("t"), 3, now);
        assert!(pool.checkout("casa", &ep("t"), now).is_some());
        assert!(pool.checkout("casa", &ep("t"), now).is_some());
        assert!(pool.checkout("casa", &ep("t"), now).is_none());
    }

    #[test]
    fn ws_pool_checkout_is_lifo() {
        let mut pool = WsPool::<u32>::new(4, Duration::from_secs(12));
        let now = Instant::now();
        pool.checkin("casa", ep("t"), 1, now);
        pool.checkin("casa", ep("t"), 2, now + Duration::from_secs(1));
        assert_eq!(pool.checkout("casa", &ep("t"), now + Duration::from_secs(2)), Some(2));
    }

    #[test]
    fn ws_pool_purge_drops_every_entry_for_the_key() {
        let mut pool = WsPool::<u32>::new(4, Duration::from_secs(12));
        let now = Instant::now();
        pool.checkin("casa", ep("t"), 1, now);
        pool.checkin("casa", ep("t"), 2, now);
        pool.checkin("mirai", ep("t"), 3, now);
        pool.purge("casa");
        assert!(pool.checkout("casa", &ep("t"), now).is_none());
        assert_eq!(pool.checkout("mirai", &ep("t"), now), Some(3));
    }

    #[test]
    fn only_clean_rpc_errors_keep_a_socket_reusable() {
        assert!(reusable_after_error("alp -32004: not-found — no session"));
        assert!(reusable_after_error("alp -32001: forbidden"));
        assert!(!reusable_after_error("websocket read: Resource temporarily unavailable"));
        assert!(!reusable_after_error("websocket closed by daemon"));
        assert!(!reusable_after_error("connect ws://10.0.0.2:49200: refused"));
        assert!(!reusable_after_error("decode: expected value at line 1"));
        assert!(!reusable_after_error("daemon returned neither result nor error"));
    }
}
