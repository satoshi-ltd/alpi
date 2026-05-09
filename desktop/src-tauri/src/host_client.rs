use std::collections::HashMap;
use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{IpAddr, SocketAddr, TcpStream};
use std::os::unix::fs::OpenOptionsExt;
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::home::resolve_root;

const READ_TIMEOUT_LOCAL_SECS: u64 = 8;
const READ_TIMEOUT_REMOTE_SECS: u64 = 20;
const STREAM_READ_TIMEOUT_SECS: u64 = 600;
const WS_CONNECT_TIMEOUT_SECS: u64 = 4;
const WS_KEEPALIVE_IDLE_SECS: u64 = 30;
const WS_KEEPALIVE_INTERVAL_SECS: u64 = 10;
const PROBE_LOCAL_TIMEOUT_MS: u64 = 400;
const PROBE_REMOTE_TIMEOUT_MS: u64 = 8000;
const PROBE_RETRY_DELAY_MS: u64 = 350;
// Sticky offline: tolerate transient blips on noisy Tailscale links.
const STICKY_OFFLINE_THRESHOLD: u32 = 2;
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
}

impl Default for StatusEntry {
    fn default() -> Self {
        Self {
            status: ConnectionStatus::Unknown,
            error: None,
            consecutive_failures: 0,
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

fn remote_ws_pool() -> &'static Mutex<HashMap<String, Arc<Mutex<WsClient>>>> {
    static POOL: OnceLock<Mutex<HashMap<String, Arc<Mutex<WsClient>>>>> = OnceLock::new();
    POOL.get_or_init(|| Mutex::new(HashMap::new()))
}

fn remote_pool_key(connection_id: &str, host: &str, port: u16, token: &str) -> String {
    format!("{connection_id}|{host}:{port}|{token}")
}

fn drop_remote_connections_for(connection_id: &str) {
    let prefix = format!("{connection_id}|");
    if let Ok(mut pool) = remote_ws_pool().lock() {
        pool.retain(|key, _| !key.starts_with(&prefix));
    }
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
    },
    Remote {
        id: String,
        name: String,
        host: String,
        port: u16,
        token: String,
        #[serde(default)]
        revoked: bool,
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

    fn with_token_redacted(&self) -> Value {
        let (status, error) = status_for(self.id());
        match self {
            HostConnection::Local { id, name } => {
                json!({
                    "id": id,
                    "name": name,
                    "kind": "local",
                    "status": status.as_str(),
                    "error": error,
                })
            }
            HostConnection::Remote {
                id,
                name,
                host,
                port,
                token,
                revoked,
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
    });
}

fn save_connections(state: &ConnectionsState) -> Result<(), String> {
    let dir = connections_dir()?;
    fs::create_dir_all(&dir).map_err(|e| format!("create {}: {e}", dir.display()))?;
    let path = connections_path()?;
    let tmp = path.with_extension("json.tmp");
    let text = serde_json::to_string_pretty(state).map_err(|e| format!("encode: {e}"))?;
    let mut f = fs::OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .mode(0o600)
        .open(&tmp)
        .map_err(|e| format!("open {}: {e}", tmp.display()))?;
    f.write_all(text.as_bytes())
        .map_err(|e| format!("write {}: {e}", tmp.display()))?;
    f.flush().ok();
    fs::rename(&tmp, &path).map_err(|e| format!("rename {}: {e}", path.display()))
}

pub fn connections_for_ui() -> Value {
    let state = load_connections();
    json!({
        "active_id": state.active_id,
        "connections": state
            .connections
            .iter()
            .map(HostConnection::with_token_redacted)
            .collect::<Vec<_>>(),
    })
}

pub fn set_active_connection(id: String) -> Result<(), String> {
    let mut state = load_connections();
    if !state.connections.iter().any(|c| c.id() == id) {
        return Err(format!("unknown connection: {id}"));
    }
    state.active_id = id;
    save_connections(&state)
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
    drop_remote_connections_for(&id);
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
    if host.trim().parse::<IpAddr>().is_err() {
        return Err("remote host must be an IP address".to_string());
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
    });
    state.active_id = id.clone();
    save_connections(&state)?;
    drop_remote_connections_for(&id);
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
        drop_remote_connections_for(id);
        if state.active_id == id {
            state.active_id = LOCAL_ID.to_string();
        }
        let _ = save_connections(&state);
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
        })
}

fn socket_path() -> Result<PathBuf, String> {
    let root = resolve_root().ok_or_else(|| "cannot resolve ~/.alpi".to_string())?;
    Ok(root.join("host").join("host.sock"))
}

pub fn call(method: &str, params: Value) -> Result<Value, String> {
    let conn = active_connection();
    let id = conn.id().to_string();
    let result = match &conn {
        HostConnection::Local { .. } => call_local_inner(
            method,
            params,
            Duration::from_secs(READ_TIMEOUT_LOCAL_SECS),
        ),
        HostConnection::Remote {
            host, port, token, ..
        } => call_remote_inner(
            &id,
            host,
            *port,
            token,
            method,
            params,
            Duration::from_secs(READ_TIMEOUT_REMOTE_SECS),
        ),
    };
    match &result {
        Ok(_) => set_status(&id, ConnectionStatus::Online, None),
        Err(e) => {
            let next = match &conn {
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
    on_frame: F,
) -> Result<(), String>
where
    F: FnMut(Value),
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

fn call_stream_local<F>(
    id: &str,
    method: &str,
    params: Value,
    mut on_frame: F,
) -> Result<(), String>
where
    F: FnMut(Value),
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

    set_status(id, ConnectionStatus::Online, None);

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
        on_frame(frame);
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
    let key = remote_pool_key(connection_id, host, port, token);
    for attempt in 0..2 {
        let ws = pooled_remote_ws(&key, host, port, timeout)?;
        let id = next_request_id();
        let request = json!({
            "id": id,
            "method": method,
            "params": with_auth(params.clone(), token),
        });
        let result = {
            let mut guard = ws
                .lock()
                .map_err(|_| "remote websocket pool poisoned".to_string())?;
            guard.set_timeout(timeout)?;
            guard.request(&id, &request)
        };
        match result {
            Ok(value) => return Ok(value),
            Err(e) if attempt == 0 && should_retry_remote_ws(&e) => {
                drop_pooled_remote_ws(&key);
                continue;
            }
            Err(e) => {
                // App-level RPC errors leave the WS intact — keep pool entry.
                if !is_app_error(&e) {
                    drop_pooled_remote_ws(&key);
                }
                return Err(e);
            }
        }
    }
    Err("remote websocket retry exhausted".to_string())
}

fn pooled_remote_ws(
    key: &str,
    host: &str,
    port: u16,
    timeout: Duration,
) -> Result<Arc<Mutex<WsClient>>, String> {
    if let Ok(pool) = remote_ws_pool().lock() {
        if let Some(ws) = pool.get(key) {
            return Ok(Arc::clone(ws));
        }
    }
    let ws = Arc::new(Mutex::new(WsClient::connect(
        host,
        port,
        Duration::from_secs(WS_CONNECT_TIMEOUT_SECS),
        timeout,
    )?));
    let mut pool = remote_ws_pool()
        .lock()
        .map_err(|_| "remote websocket pool poisoned".to_string())?;
    Ok(Arc::clone(pool.entry(key.to_string()).or_insert(ws)))
}

fn drop_pooled_remote_ws(key: &str) {
    if let Ok(mut pool) = remote_ws_pool().lock() {
        pool.remove(key);
    }
}

fn should_retry_remote_ws(err: &str) -> bool {
    !err.contains("auth-failed")
        && (err.starts_with("websocket ")
            || err.starts_with("connect ")
            || err.starts_with("set read timeout")
            || err.starts_with("set write timeout"))
}

// "alp -3200X: ..." = JSON-RPC error from the daemon. The WS is fine; keep pool.
fn is_app_error(err: &str) -> bool {
    err.starts_with("alp ")
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
    F: FnMut(Value),
{
    let mut ws = WsClient::connect(
        host,
        port,
        Duration::from_secs(WS_CONNECT_TIMEOUT_SECS),
        Duration::from_secs(STREAM_READ_TIMEOUT_SECS),
    )?;
    set_status(connection_id, ConnectionStatus::Online, None);
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
        on_frame(frame);
        if done {
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

fn socket_addr(host: &str, port: u16) -> Result<SocketAddr, String> {
    let ip = host
        .parse::<IpAddr>()
        .map_err(|_| "remote host must be an IP address".to_string())?;
    Ok(SocketAddr::new(ip, port))
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
        let addr = socket_addr(host, port)?;
        let stream = TcpStream::connect_timeout(&addr, connect_timeout)
            .map_err(|e| format!("connect ws://{host}:{port}: {e}"))?;
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

    fn set_timeout(&mut self, timeout: Duration) -> Result<(), String> {
        self.stream
            .set_read_timeout(Some(timeout))
            .map_err(|e| format!("set read timeout: {e}"))?;
        self.stream
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

// Remote probes retry once after PROBE_RETRY_DELAY_MS; auth failures and local probes don't.
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
        if matches!(conn, HostConnection::Remote { .. })
            && classify_remote_error(e) != ConnectionStatus::AuthFailed
        {
            std::thread::sleep(Duration::from_millis(PROBE_RETRY_DELAY_MS));
            result = probe_once();
        }
    }
    match result {
        Ok(_) => set_status(&id, ConnectionStatus::Online, None),
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
        };
        let remote = HostConnection::Remote {
            id: "remote-1".to_string(),
            name: "Remote".to_string(),
            host: "10.0.0.2".to_string(),
            port: 49200,
            token: "secret".to_string(),
            revoked: false,
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
    fn remote_socket_addr_rejects_hostnames() {
        assert!(socket_addr("100.64.0.1", 49200).is_ok());
        assert!(socket_addr("MacBook-Pro.local", 49200).is_err());
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
    fn is_app_error_only_matches_alp_rpc_errors() {
        assert!(is_app_error("alp -32000: auth-failed"));
        assert!(is_app_error("alp -32004: not-found"));
        assert!(is_app_error("alp -1: anything"));
        assert!(!is_app_error("websocket closed by daemon"));
        assert!(!is_app_error("connect ws://1.2.3.4:80: refused"));
        assert!(!is_app_error("set read timeout: foo"));
        assert!(!is_app_error("remote websocket pool poisoned"));
    }

    // The pool entry must survive an app-level error so the next call
    // doesn't pay the WS handshake again. Manipulate the pool directly
    // and apply the same eviction rule call_remote_inner uses.
    #[test]
    fn pool_survives_app_error_but_drops_on_transport_error() {
        let key_app = "test-app-error";
        let key_transport = "test-transport-error";

        // Seed both pool entries with placeholder TcpStreams pointing at a
        // local TcpListener so the inner WsClient construction is valid.
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        for key in [key_app, key_transport] {
            let stream = std::net::TcpStream::connect(addr).unwrap();
            let ws = std::sync::Arc::new(std::sync::Mutex::new(WsClient { stream }));
            remote_ws_pool().lock().unwrap().insert(key.to_string(), ws);
        }
        // Simulate the eviction decision call_remote_inner makes.
        let app_err = "alp -32004: not-found";
        let transport_err = "websocket closed by daemon";
        if !is_app_error(app_err) {
            drop_pooled_remote_ws(key_app);
        }
        if !is_app_error(transport_err) {
            drop_pooled_remote_ws(key_transport);
        }
        let pool = remote_ws_pool().lock().unwrap();
        assert!(
            pool.contains_key(key_app),
            "app-level error must NOT evict the pool entry",
        );
        assert!(
            !pool.contains_key(key_transport),
            "transport error must evict the pool entry",
        );
    }
}
