use serde::Serialize;
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager};
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
    let _ = app
        .notification()
        .builder()
        .title(title)
        .body(body)
        .show();
}

pub fn dispatch_daemon_frame(app: &AppHandle, frame: &serde_json::Value) {
    let event = frame.get("event").and_then(|v| v.as_str()).unwrap_or("");
    let data = frame
        .get("data")
        .cloned()
        .unwrap_or(serde_json::Value::Null);
    match event {
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
        "schedule.done" | "schedule.failed" => {
            let ok = event == "schedule.done";
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
            let title = if ok {
                format!("{} · schedule ran", profile)
            } else {
                format!("{} · schedule failed", profile)
            };
            let body = if msg.is_empty() {
                job_id.clone()
            } else {
                format!("{}: {}", job_id, msg)
            };
            show(
                app,
                &title,
                &body,
                Deeplink {
                    kind: "settings".into(),
                    profile: Some(profile),
                    id: Some("schedules".into()),
                },
            );
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
    if window_focused(app)
        && (is_active("chat", session_id) || is_active("chat-new", profile))
    {
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
