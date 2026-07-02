use std::collections::HashMap;
use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{IpAddr, SocketAddr, TcpStream, ToSocketAddrs};
#[cfg(unix)]
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex, OnceLock};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[cfg(unix)]
use crate::home::resolve_root;

#[cfg(not(unix))]
const LOCAL_UNSUPPORTED: &str =
    "local daemon connections aren't supported on Windows yet — pair a remote daemon over Tailscale";

// RPC timeouts stay generous — a busy daemon or slow Tailscale hop must not fail falsely (calls run off the main thread, so nothing freezes); dead-daemon detection belongs to the probes (2.5s local / 8s remote — a just-restarted daemon's warmup must not read as offline) and the stream keepalives (events ping 25s, chat heartbeat 5s → 75s = three missed pings).
const READ_TIMEOUT_LOCAL_SECS: u64 = 8;
const READ_TIMEOUT_REMOTE_SECS: u64 = 20;
const STREAM_READ_TIMEOUT_SECS: u64 = 75;
const WS_CONNECT_TIMEOUT_SECS: u64 = 4;
const WS_KEEPALIVE_IDLE_SECS: u64 = 30;
const WS_KEEPALIVE_INTERVAL_SECS: u64 = 10;
const PROBE_LOCAL_TIMEOUT_MS: u64 = 2500;
const PROBE_REMOTE_TIMEOUT_MS: u64 = 8000;
const PROBE_RETRY_DELAY_MS: u64 = 350;
// Sticky offline: tolerate transient blips on noisy Tailscale links.
const STICKY_OFFLINE_THRESHOLD: u32 = 2;
// Bound concurrent request/response RPCs per remote connection so a Settings fan-out (or 10 remotes) can't open a burst of sockets at once. Local socket and streams are uncapped.
const MAX_INFLIGHT_PER_REMOTE: usize = 4;
const CONNECTIONS_FILE: &str = "connections.json";
pub const LOCAL_ID: &str = "local";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionStatus {
    Unknown,
    Probing,
    Online,
    Offline,
    AuthFailed,
}

impl ConnectionStatus {
    fn as_str(&self) -> &'static str {
        match self {
            ConnectionStatus::Unknown => "unknown",
            ConnectionStatus::Probing => "probing",
            ConnectionStatus::Online => "online",
            ConnectionStatus::Offline => "offline",
            ConnectionStatus::AuthFailed => "auth-failed",
        }
    }
}

#[derive(Debug, Clone)]
struct StatusEntry {
    status: ConnectionStatus,
    error: Option<String>,
    consecutive_failures: u32,
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

// Online → Offline only flips after STICKY_OFFLINE_THRESHOLD consecutive failures.
fn set_status(id: &str, status: ConnectionStatus, error: Option<String>) {
    let mut transitioned = false;
    if let Ok(mut map) = status_map().lock() {
        let entry = map.entry(id.to_string()).or_default();
        match status {
            ConnectionStatus::Offline if entry.status == ConnectionStatus::Online => {
                entry.consecutive_failures = entry.consecutive_failures.saturating_add(1);
                if entry.consecutive_failures < STICKY_OFFLINE_THRESHOLD {
                    return;
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
        return;
    }
    if let Ok(guard) = listeners().lock() {
        for listener in guard.iter() {
            listener(id, status, error.as_deref());
        }
    }
}

fn classify_remote_error(err: &str) -> ConnectionStatus {
    if err.contains("auth-failed") {
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
        .and_then(|d| d.get("summary").or_else(|| d.get("detail")))
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
    },
    Remote {
        id: String,
        name: String,
        host: String,
        port: u16,
        token: String,
        #[serde(default)]
        revoked: bool,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        device_id: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        last_connected: Option<i64>,
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

    fn with_token_redacted(&self) -> Value {
        let (status, error) = status_for(self.id());
        let alpi_version = version_for(self.id());
        let update_available = update_available_for(self.id());
        let role = role_for(self.id());
        match self {
            HostConnection::Local { id, name, device_id, last_connected } => {
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
            } => json!({
                "id": id,
                "name": name,
                "kind": "remote",
                "host": host,
                "port": port,
                "token_id": token.chars().rev().take(8).collect::<String>().chars().rev().collect::<String>(),
                "revoked": revoked,
                "status": status.as_str(),
                "error": error,
                "alpi_version": alpi_version,
                "update_available": update_available,
                "device_id": device_id,
                "role": role,
                "last_connected": last_connected,
            }),
        }
    }
}

fn connections_dir() -> Result<PathBuf, String> {
    dirs::config_dir()
        .map(|p| p.join("alpi-desktop"))
        .ok_or_else(|| "cannot resolve config dir".to_string())
}

fn connections_path() -> Result<PathBuf, String> {
    Ok(connections_dir()?.join(CONNECTIONS_FILE))
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
    let mut state: ConnectionsState = match serde_json::from_str(&text) {
        Ok(s) => s,
        Err(_) => return ConnectionsState::default(),
    };
    ensure_local(&mut state);
    if !state.connections.iter().any(|c| c.id() == state.active_id) {
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
    });
}

pub fn active_subscription_key() -> Option<String> {
    let state = load_connections();
    let active = state.connections.iter().find(|c| c.id() == state.active_id)?;
    active.device_id().map(|d| format!("daemon:{d}"))
}

fn persist_device_id(connection_id: &str, device_id: &str) {
    let mut state = load_connections();
    let mut changed = false;
    for conn in state.connections.iter_mut() {
        if conn.id() == connection_id {
            if conn.device_id() != Some(device_id) {
                conn.set_device_id(Some(device_id.to_string()));
                changed = true;
            }
            break;
        }
    }
    if changed {
        let _ = save_connections(&state);
    }
}

fn persist_last_connected(connection_id: &str) {
    let mut state = load_connections();
    let mut changed = false;
    for conn in state.connections.iter_mut() {
        if conn.id() == connection_id {
            conn.set_last_connected(Some(now_unix()));
            changed = true;
            break;
        }
    }
    if changed {
        let _ = save_connections(&state);
    }
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
    let text = serde_json::to_string_pretty(state).map_err(|e| format!("encode: {e}"))?;
    let mut f = open_private(&tmp)
        .map_err(|e| format!("open {}: {e}", tmp.display()))?;
    f.write_all(text.as_bytes())
        .map_err(|e| format!("write {}: {e}", tmp.display()))?;
    f.flush().ok();
    fs::rename(&tmp, &path).map_err(|e| format!("rename {}: {e}", path.display()))
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
    let mut state = load_connections();
    if !state.connections.iter().any(|c| c.id() == id) {
        return Err(format!("unknown connection: {id}"));
    }
    state.active_id = id;
    save_connections(&state)?;
    Ok(())
}

pub fn forget_connection(id: String) -> Result<(), String> {
    if id == LOCAL_ID {
        return Err("local connection cannot be removed".to_string());
    }
    let mut state = load_connections();
    state.connections.retain(|c| c.id() != id);
    if state.active_id == id {
        state.active_id = LOCAL_ID.to_string();
    }
    save_connections(&state)?;
    if let Ok(mut map) = status_map().lock() {
        map.remove(&id);
    }
    Ok(())
}

pub fn add_remote_connection(
    name: String,
    host: String,
    port: u16,
    token: String,
) -> Result<String, String> {
    if host.trim().is_empty() {
        return Err("host is required".to_string());
    }
    if !is_valid_host(host.trim()) {
        return Err("remote host must be an IP address or hostname".to_string());
    }
    if token.trim().is_empty() {
        return Err("token is required".to_string());
    }
    let id = format!(
        "remote-{}-{}",
        host.trim().replace(|c: char| !c.is_ascii_alphanumeric(), "-"),
        port,
    );
    let mut state = load_connections();
    state.connections.retain(|c| c.id() != id);
    state.connections.push(HostConnection::Remote {
        id: id.clone(),
        name: if name.trim().is_empty() {
            host.trim().to_string()
        } else {
            name.trim().to_string()
        },
        host: host.trim().to_string(),
        port,
        token: token.trim().to_string(),
        revoked: false,
        device_id: None,
        last_connected: None,
    });
    state.active_id = id.clone();
    save_connections(&state)?;
    Ok(id)
}

pub fn mark_connection_revoked(id: &str) {
    let mut state = load_connections();
    let mut changed = false;
    for c in &mut state.connections {
        if let HostConnection::Remote { id: cid, revoked, .. } = c {
            if cid == id && !*revoked {
                *revoked = true;
                changed = true;
            }
        }
    }
    if changed {
        if state.active_id == id {
            state.active_id = LOCAL_ID.to_string();
        }
        let _ = save_connections(&state);
    }
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

pub fn call(method: &str, params: Value) -> Result<Value, String> {
    call_conn(&active_connection(), method, params)
}

// Same as `call`, but routed to a specific connection regardless of which is active.
pub fn call_for(connection_id: &str, method: &str, params: Value) -> Result<Value, String> {
    let conn = connection_by_id(connection_id)
        .ok_or_else(|| format!("unknown connection: {connection_id}"))?;
    call_conn(&conn, method, params)
}

fn call_conn(conn: &HostConnection, method: &str, params: Value) -> Result<Value, String> {
    let id = conn.id().to_string();
    let result = match conn {
        HostConnection::Local { .. } => call_local_inner(
            method,
            params,
            Duration::from_secs(READ_TIMEOUT_LOCAL_SECS),
        ),
        HostConnection::Remote {
            host, port, token, ..
        } => {
            let _slot = acquire_remote_slot(&id);
            call_remote_inner(
                host,
                *port,
                token,
                method,
                params,
                Duration::from_secs(READ_TIMEOUT_REMOTE_SECS),
            )
        }
    };
    match &result {
        Ok(_) => set_status(&id, ConnectionStatus::Online, None),
        Err(e) => {
            let next = match conn {
                HostConnection::Local { .. } => classify_local_error(e),
                HostConnection::Remote { .. } => {
                    let cls = classify_remote_error(e);
                    if cls == ConnectionStatus::AuthFailed {
                        mark_connection_revoked(&id);
                    }
                    cls
                }
            };
            set_status(&id, next, Some(e.clone()));
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
            "alpi daemon socket not found at {} — is the host subsystem enabled (alpi setup → Service → Subsystems)?",
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
            "alpi daemon socket not found at {} — is the host subsystem enabled (alpi setup → Service → Subsystems)?",
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
    let mut online = false;
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
        if !online {
            // Online only once the daemon actually replies — connecting to a still-booting daemon must not flap Online→Offline.
            set_status(id, ConnectionStatus::Online, None);
            online = true;
        }
        if !on_frame(frame) {
            break;
        }
    }
    Ok(())
}

fn call_remote_inner(
    host: &str,
    port: u16,
    token: &str,
    method: &str,
    params: Value,
    timeout: Duration,
) -> Result<Value, String> {
    retry_remote(|| call_remote_once(host, port, token, method, params.clone(), timeout))
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
    let mut online = false;
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
        let auth_failed = frame
            .get("error")
            .and_then(|err| {
                Some((
                    err.get("code")?.as_i64()?,
                    err.get("message")?.as_str()?.to_string(),
                ))
            })
            .map(|(code, message)| code == -32000 && message == "auth-failed")
            .unwrap_or(false);
        if auth_failed {
            mark_connection_revoked(connection_id);
            return Err("alp -32000: auth-failed".to_string());
        }
        if !online {
            // Online only once the daemon actually replies — mirrors the local stream.
            set_status(connection_id, ConnectionStatus::Online, None);
            online = true;
        }
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

struct WsClient {
    stream: TcpStream,
}

impl WsClient {
    fn connect(
        host: &str,
        port: u16,
        connect_timeout: Duration,
        read_timeout: Duration,
    ) -> Result<Self, String> {
        let addrs = resolve_addrs(host, port)?;
        let mut stream = None;
        let mut last_err = format!("connect ws://{host}:{port}: no address");
        for addr in &addrs {
            match TcpStream::connect_timeout(addr, connect_timeout) {
                Ok(s) => {
                    stream = Some(s);
                    break;
                }
                Err(e) => last_err = format!("connect ws://{host}:{port} ({addr}): {e}"),
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
        let mut stream = stream;
        stream
            .set_read_timeout(Some(read_timeout))
            .map_err(|e| format!("set read timeout: {e}"))?;
        stream
            .set_write_timeout(Some(read_timeout))
            .map_err(|e| format!("set write timeout: {e}"))?;
        let key = "dGhlIHNhbXBsZSBub25jZQ==";
        let req = format!(
            "GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
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
        Ok(Self { stream })
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
                    return String::from_utf8(payload)
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

// Both transports retry once after PROBE_RETRY_DELAY_MS before flipping; only a rejected token (auth-failed) skips the retry.
pub fn probe_connection(conn: &HostConnection) {
    let id = conn.id().to_string();
    set_status(&id, ConnectionStatus::Probing, None);
    let timeout = probe_timeout_for(conn);
    let probe_once = || match conn {
        HostConnection::Local { .. } => {
            call_local_inner("host.profiles.list", json!({}), timeout)
        }
        HostConnection::Remote {
            host, port, token, ..
        } => call_remote_once(
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
                classify_remote_error(e) != ConnectionStatus::AuthFailed
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
            let version_call = match conn {
                HostConnection::Local { .. } => {
                    call_local_inner("host.version", json!({}), timeout)
                }
                HostConnection::Remote {
                    host, port, token, ..
                } => call_remote_once(
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
            set_role(&id, role);
            let device_id = version_value
                .as_ref()
                .and_then(|v| v.get("device_id"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(|s| s.to_string());
            if let Some(did) = device_id {
                persist_device_id(&id, &did);
            }
        }
        Err(e) => {
            let next = match conn {
                HostConnection::Local { .. } => ConnectionStatus::Offline,
                HostConnection::Remote { .. } => {
                    let cls = classify_remote_error(&e);
                    if cls == ConnectionStatus::AuthFailed {
                        mark_connection_revoked(&id);
                    }
                    cls
                }
            };
            set_status(&id, next, Some(e));
            set_version(&id, None);
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn probe_timeout_is_shorter_for_local_connections() {
        let local = HostConnection::Local {
            id: LOCAL_ID.to_string(),
            name: "Local daemon".to_string(),
            device_id: None,
            last_connected: None,
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
        };
        assert_eq!(remote.device_id(), Some("uuid-mac"));
        remote.set_device_id(None);
        assert!(remote.device_id().is_none());
    }

    #[test]
    fn classify_remote_errors() {
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
        };
        let conns = vec![
            remote("r-old", Some(100)),
            HostConnection::Local {
                id: LOCAL_ID.to_string(),
                name: "Local".to_string(),
                device_id: None,
                last_connected: None,
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

}
