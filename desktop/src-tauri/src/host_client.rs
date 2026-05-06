use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::os::unix::net::UnixStream;
use std::os::unix::fs::OpenOptionsExt;
use std::path::PathBuf;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::home::resolve_root;

const READ_TIMEOUT_SECS: u64 = 30;
const STREAM_READ_TIMEOUT_SECS: u64 = 600;
const CONNECTIONS_FILE: &str = "connections.json";
const LOCAL_ID: &str = "local";

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
    fn id(&self) -> &str {
        match self {
            HostConnection::Local { id, .. } => id,
            HostConnection::Remote { id, .. } => id,
        }
    }

    fn with_token_redacted(&self) -> Value {
        match self {
            HostConnection::Local { id, name } => {
                json!({"id": id, "name": name, "kind": "local"})
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
    save_connections(&state)
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
    match active_connection() {
        HostConnection::Local { .. } => call_local(method, params),
        HostConnection::Remote {
            id,
            host, port, token, ..
        } => call_remote(&id, &host, port, &token, method, params),
    }
}

fn call_local(method: &str, params: Value) -> Result<Value, String> {
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
        .set_read_timeout(Some(Duration::from_secs(READ_TIMEOUT_SECS)))
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
        return Err(format!("alp {}: {}", err.code, err.message));
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
    match active_connection() {
        HostConnection::Local { .. } => call_stream_local(method, params, on_frame),
        HostConnection::Remote {
            id,
            host, port, token, ..
        } => call_stream_remote(&id, &host, port, &token, method, params, on_frame),
    }
}

fn call_stream_local<F>(
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

fn call_remote(
    connection_id: &str,
    host: &str,
    port: u16,
    token: &str,
    method: &str,
    params: Value,
) -> Result<Value, String> {
    let mut ws = WsClient::connect(host, port, READ_TIMEOUT_SECS)?;
    let id = "tauri-1";
    ws.send_json(&json!({
        "id": id,
        "method": method,
        "params": with_auth(params, token),
    }))?;
    loop {
        let frame = ws.read_text()?;
        let response: ControlResponse =
            serde_json::from_str(&frame).map_err(|e| format!("decode: {e}"))?;
        if !frame_matches_id(&frame, id) {
            continue;
        }
        if let Some(err) = response.error {
            if err.code == -32000 && err.message == "auth-failed" {
                mark_connection_revoked(connection_id);
            }
            return Err(format!("alp {}: {}", err.code, err.message));
        }
        return response
            .result
            .ok_or_else(|| "daemon returned neither result nor error".to_string());
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
    F: FnMut(Value),
{
    let mut ws = WsClient::connect(host, port, STREAM_READ_TIMEOUT_SECS)?;
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
        if frame
            .get("error")
            .and_then(|err| {
                Some((
                    err.get("code")?.as_i64()?,
                    err.get("message")?.as_str()?.to_string(),
                ))
            })
            .map(|(code, message)| code == -32000 && message == "auth-failed")
            .unwrap_or(false)
        {
            mark_connection_revoked(connection_id);
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

struct WsClient {
    stream: TcpStream,
}

impl WsClient {
    fn connect(host: &str, port: u16, timeout_secs: u64) -> Result<Self, String> {
        let mut stream = TcpStream::connect((host, port))
            .map_err(|e| format!("connect ws://{host}:{port}: {e}"))?;
        stream
            .set_read_timeout(Some(Duration::from_secs(timeout_secs)))
            .map_err(|e| format!("set read timeout: {e}"))?;
        stream
            .set_write_timeout(Some(Duration::from_secs(READ_TIMEOUT_SECS)))
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
            return Err(format!("websocket handshake failed: {}", head.lines().next().unwrap_or("")));
        }
        Ok(Self { stream })
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
