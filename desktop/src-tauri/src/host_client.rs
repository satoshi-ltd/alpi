use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::time::Duration;

use serde::Deserialize;
use serde_json::{json, Value};

use crate::home::resolve_root;

const READ_TIMEOUT_SECS: u64 = 30;
const STREAM_READ_TIMEOUT_SECS: u64 = 600;

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

fn socket_path() -> Result<PathBuf, String> {
    let root = resolve_root().ok_or_else(|| "cannot resolve ~/.alpi".to_string())?;
    Ok(root.join("host").join("host.sock"))
}

pub fn call(method: &str, params: Value) -> Result<Value, String> {
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
