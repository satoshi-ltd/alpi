use serde::Serialize;
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager};
#[cfg(not(all(debug_assertions, target_os = "macos")))]
use tauri_plugin_notification::NotificationExt;

static ACTIVE_VIEW: Mutex<Option<(String, String)>> = Mutex::new(None);
static LAST_DISCONNECT: Mutex<Option<Instant>> = Mutex::new(None);

pub fn set_active_view(kind: Option<String>, id: Option<String>) {
    let mut v = ACTIVE_VIEW.lock().unwrap();
    *v = match (kind, id) {
        (Some(k), Some(i)) if !k.is_empty() && !i.is_empty() => Some((k, i)),
        _ => None,
    };
}

fn is_active(kind: &str, id: &str) -> bool {
    ACTIVE_VIEW
        .lock()
        .unwrap()
        .as_ref()
        .map(|(k, i)| k == kind && i == id)
        .unwrap_or(false)
}

fn window_focused(app: &AppHandle) -> bool {
    app.get_webview_window("main")
        .and_then(|w| w.is_focused().ok())
        .unwrap_or(false)
}

#[derive(Serialize, Clone)]
pub struct Deeplink {
    pub kind: String,
    pub profile: Option<String>,
    pub id: Option<String>,
}

fn show(app: &AppHandle, title: &str, body: &str, deeplink: Deeplink) {
    // Plugin has no per-notification click callback; React consumes the deeplink on next window focus.
    let payload = serde_json::json!({
        "title": title,
        "body": body,
        "deeplink": deeplink,
        "fired_at": chrono::Utc::now().timestamp_millis(),
    });
    let _ = app.emit("notification-fired", payload);

    #[cfg(all(debug_assertions, target_os = "macos"))]
    {
        // `tauri dev` runs unsigned; macOS Notification Center blocks the plugin silently. Fall back to osascript which uses the system Script Editor identity — no signing or permission grant needed for verification.
        let _ = show_via_osascript(title, body);
    }
    #[cfg(not(all(debug_assertions, target_os = "macos")))]
    {
        let _ = app
            .notification()
            .builder()
            .title(title)
            .body(body)
            .show();
    }
}

#[cfg(all(debug_assertions, target_os = "macos"))]
fn show_via_osascript(title: &str, body: &str) -> std::io::Result<()> {
    let escape = |s: &str| s.replace('\\', "\\\\").replace('"', "\\\"");
    let script = format!(
        r#"display notification "{}" with title "{}""#,
        escape(body),
        escape(title),
    );
    std::process::Command::new("osascript")
        .arg("-e")
        .arg(script)
        .spawn()
        .map(|_| ())
}

pub fn dispatch_daemon_frame(app: &AppHandle, frame: &serde_json::Value) {
    let event = frame.get("event").and_then(|v| v.as_str()).unwrap_or("");
    let data = frame
        .get("data")
        .cloned()
        .unwrap_or(serde_json::Value::Null);
    match event {
        "approval.request" => {
            // Skip native banner when window focused — App.jsx's ApprovalSheet modal already pops, banner would be a duplicate.
            if window_focused(app) {
                return;
            }
            let profile = data
                .get("profile")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let command = data
                .get("command")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .trim();
            let pattern = data
                .get("pattern")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let severity = data
                .get("severity")
                .and_then(|v| v.as_str())
                .unwrap_or("caution");
            let request_id = data
                .get("request_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let title = format!("{} · approval needed ({})", profile, severity);
            let body = if !command.is_empty() {
                command.to_string()
            } else if !pattern.is_empty() {
                pattern.to_string()
            } else {
                "Tool execution awaiting approval.".to_string()
            };
            show(
                app,
                &title,
                &body,
                Deeplink {
                    kind: "approval".into(),
                    profile: Some(profile),
                    id: Some(request_id),
                },
            );
        }
        "wg.done" => {
            let profile = data
                .get("profile")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let wg_id = data
                .get("wg_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            // Gate is_active on focus: ACTIVE_VIEW stays set after blur, so alone it's stale.
            if window_focused(app) && is_active("workgroup", &wg_id) {
                return;
            }
            let summary = data
                .get("summary")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let body = summary
                .trim()
                .strip_prefix("#done")
                .unwrap_or(summary)
                .trim();
            let body = if body.is_empty() { "(no summary)" } else { body };
            let title = format!("{} · #done", profile);
            show(
                app,
                &title,
                body,
                Deeplink {
                    kind: "workgroup".into(),
                    profile: Some(profile),
                    id: Some(wg_id),
                },
            );
        }
        "schedule.failed" => {
            // schedule.done success doesn't notify natively; jobs that want to interrupt call send_message(channel="alpi"). Only failures wake the user.
            let profile = data
                .get("profile")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let job_id = data
                .get("job_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let msg = data.get("message").and_then(|v| v.as_str()).unwrap_or("");
            let title = format!("{} · schedule failed", profile);
            let body = if msg.is_empty() {
                job_id.clone()
            } else {
                format!("{}: {}", job_id, msg)
            };
            let output_id = data
                .get("output_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            // output_id is the v0.6.11+ path; fall back to the schedule list for older daemons.
            let deeplink = if !output_id.is_empty() {
                Deeplink {
                    kind: "output".into(),
                    profile: Some(profile),
                    id: Some(output_id),
                }
            } else {
                Deeplink {
                    kind: "settings".into(),
                    profile: Some(profile),
                    id: Some("schedules".into()),
                }
            };
            show(app, &title, &body, deeplink);
        }
        "agent.message" => {
            let profile = data
                .get("profile")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let title = data
                .get("title")
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(|s| s.to_string())
                .unwrap_or_else(|| profile.clone());
            let body = data
                .get("body")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .trim()
                .to_string();
            if body.is_empty() {
                return;
            }
            let output_id = data
                .get("output_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let session_id = data
                .get("session_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            if window_focused(app) && !session_id.is_empty() && is_active("chat", &session_id) {
                return;
            }
            // output_id is the v0.6.11+ path; older daemons fall back to the chat/profile deeplink.
            let deeplink = if !output_id.is_empty() {
                Deeplink {
                    kind: "output".into(),
                    profile: Some(profile),
                    id: Some(output_id),
                }
            } else if !session_id.is_empty() {
                Deeplink {
                    kind: "chat".into(),
                    profile: Some(profile),
                    id: Some(session_id),
                }
            } else {
                Deeplink {
                    kind: "profile".into(),
                    profile: Some(profile),
                    id: None,
                }
            };
            show(app, &title, &body, deeplink);
        }
        "budget.threshold" => {
            let profile = data
                .get("profile")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let level = data.get("level").and_then(|v| v.as_str()).unwrap_or("?");
            let used = data
                .get("used_usd")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let cap = data.get("cap_usd").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let title = format!("{} · {}% daily budget", profile, level);
            let body = format!("${:.2} / ${:.2}", used, cap);
            show(
                app,
                &title,
                &body,
                Deeplink {
                    kind: "settings".into(),
                    profile: Some(profile),
                    id: Some("budget".into()),
                },
            );
        }
        _ => {}
    }
}

pub fn dispatch_session_done(app: &AppHandle, profile: &str, session_id: &str) {
    // Skip when focused — emitting a deeplink here yanks the user back on next focus change.
    if window_focused(app) {
        return;
    }
    let title = format!("{} · reply ready", profile);
    show(
        app,
        &title,
        "tap to open the conversation",
        Deeplink {
            kind: "chat".into(),
            profile: Some(profile.to_string()),
            id: Some(session_id.to_string()),
        },
    );
}

pub fn dispatch_daemon_disconnect(app: &AppHandle, connection_id: &str) {
    let mut last = LAST_DISCONNECT.lock().unwrap();
    if let Some(t) = *last {
        if t.elapsed() < Duration::from_secs(30) {
            return;
        }
    }
    *last = Some(Instant::now());
    show(
        app,
        "alpi daemon disconnected",
        &format!("connection: {}", connection_id),
        Deeplink {
            kind: "settings".into(),
            profile: None,
            id: Some("connection".into()),
        },
    );
}
