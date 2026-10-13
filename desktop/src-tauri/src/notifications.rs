use serde::Serialize;
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager};
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

const ACTIVATION_WINDOW: Duration = Duration::from_secs(20);
static PENDING_ACTIVATION: Mutex<Option<(Deeplink, Instant)>> = Mutex::new(None);

fn activation_rank(deeplink: &Deeplink) -> u8 {
    match (deeplink.kind.as_str(), deeplink.id.as_deref()) {
        ("approval" | "clarification", _) => 2,
        ("settings", Some("schedules")) => 1,
        ("settings", _) => 0,
        _ => 1,
    }
}

fn remember_for_activation(deeplink: &Deeplink, window_was_focused: bool, now: Instant) {
    let mut pending = PENDING_ACTIVATION.lock().unwrap();
    if window_was_focused {
        *pending = None;
        return;
    }
    let rank = activation_rank(deeplink);
    if rank == 0 {
        return;
    }
    let held_by_request = pending
        .as_ref()
        .is_some_and(|(held, at)| activation_rank(held) > rank && now.saturating_duration_since(*at) <= ACTIVATION_WINDOW);
    if !held_by_request {
        *pending = Some((deeplink.clone(), now));
    }
}

pub fn clear_activation() {
    PENDING_ACTIVATION.lock().unwrap().take();
}

pub fn take_activation(now: Instant) -> Option<Deeplink> {
    let pending = PENDING_ACTIVATION.lock().unwrap().take();
    pending.and_then(|(deeplink, at)| (now.saturating_duration_since(at) <= ACTIVATION_WINDOW).then_some(deeplink))
}

#[derive(Serialize, Clone)]
pub struct Deeplink {
    pub kind: String,
    pub profile: Option<String>,
    pub id: Option<String>,
    // Origin connection — the React side switches to it before applying the view.
    pub connection_id: String,
}

fn profile_handle(profile: &str) -> String {
    match profile.trim() {
        "" => String::new(),
        "default" => "@alpi".to_string(),
        name => format!("@{}", name),
    }
}

const NO_PROSE: &str = "Open it to read the detail.";

fn strip_inline_marks(text: &str) -> String {
    text.replace("**", "").replace('`', "")
}

fn strip_line_marks(line: &str) -> &str {
    let mut rest = line.trim_start();
    loop {
        let hashes = rest.len() - rest.trim_start_matches('#').len();
        let after = &rest[hashes..];
        if (1..=6).contains(&hashes) && after.starts_with(char::is_whitespace) {
            rest = after.trim_start();
        } else if let Some(after) = ["> ", "- ", "* ", "• ", "| "].iter().find_map(|mark| rest.strip_prefix(mark)) {
            rest = after.trim_start();
        } else {
            return rest;
        }
    }
}

fn clean_title(title: &str, legacy: bool) -> String {
    let title = strip_line_marks(title.trim());
    if legacy { strip_inline_marks(title).trim().to_string() } else { title.trim().to_string() }
}

fn is_rule_line(line: &str) -> bool {
    line.chars().all(|c| matches!(c, '-' | '|' | ':' | ' ' | '*' | '_'))
}

// Older daemons send no summary, so the banner takes the body's first readable line instead of its raw markdown.
fn is_heading(line: &str) -> bool {
    let hashes = line.len() - line.trim_start_matches('#').len();
    (1..=6).contains(&hashes) && line[hashes..].starts_with(char::is_whitespace)
}

fn first_readable_line(body: &str) -> String {
    let mut fence = false;
    let mut heading = String::new();
    for raw in body.lines() {
        let line = raw.trim();
        if line.starts_with("```") || line.starts_with("~~~") {
            fence = !fence;
            continue;
        }
        if fence || line.is_empty() || line.starts_with('|') || is_rule_line(line) {
            continue;
        }
        let text = strip_inline_marks(strip_line_marks(line)).trim().to_string();
        if text.is_empty() {
            continue;
        }
        if !is_heading(line) {
            return text;
        }
        if heading.is_empty() {
            heading = text;
        }
    }
    heading
}

// The daemon sends the profile name as the title when the row has none, so that value means "untitled".
fn notification_lines(title: &str, summary: Option<&str>, body: &str, level: &str, profile: &str) -> (String, String) {
    let handle = profile_handle(profile);
    let title = if title.trim() == profile.trim() { String::new() } else { clean_title(title, summary.is_none()) };
    let head = match (handle.is_empty(), title.is_empty()) {
        (true, _) => title,
        (false, true) => handle,
        (false, false) => format!("{} · {}", handle, title),
    };
    let text = match summary.map(str::trim) {
        Some(given) if !given.is_empty() => given.to_string(),
        _ if body.trim().is_empty() => String::new(),
        Some(_) => NO_PROSE.to_string(),
        None => {
            let line = first_readable_line(body);
            if line.is_empty() { NO_PROSE.to_string() } else { line }
        }
    };
    let prefix = match level {
        "warning" => "Warning · ",
        "error" => "Failed · ",
        _ => "",
    };
    let line = if text.is_empty() { String::new() } else { format!("{}{}", prefix, text) };
    (head, line)
}

// Polled and replayed frames only: the daemon auto-resolves a request at ts + timeout_s, and a live frame must not hinge on clock skew between hosts.
fn request_expired(data: &serde_json::Value, now_secs: f64) -> bool {
    let ts = data.get("ts").and_then(|v| v.as_f64());
    let timeout = data.get("timeout_s").and_then(|v| v.as_f64());
    match (ts, timeout) {
        (Some(ts), Some(timeout)) if timeout > 0.0 => now_secs > ts + timeout,
        _ => false,
    }
}

fn replay_expired(frame: &serde_json::Value, now: f64) -> bool {
    let kind = frame.get("event").and_then(|v| v.as_str()).unwrap_or("");
    let data = frame.get("data").cloned().unwrap_or(serde_json::Value::Null);
    matches!(kind, "approval.request" | "clarification.request") && request_expired(&data, now)
}

pub fn dispatch_replayed_frame(app: &AppHandle, connection_id: &str, frame: &serde_json::Value) {
    if replay_expired(frame, now_secs()) {
        return;
    }
    dispatch_daemon_frame(app, connection_id, true, frame);
}

fn now_secs() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn clarification_lines(profile: &str, question: &str) -> (String, String) {
    let title = if profile.is_empty() { "question".to_string() } else { format!("{} · question", profile) };
    let body = if question.is_empty() { "Your agent is waiting for an answer.".to_string() } else { question.to_string() };
    (title, body)
}

fn schedule_failure_body(name: &str, reason: &str) -> String {
    let reason = reason.replace('\n', " · ");
    let reason = reason.trim();
    let name = name.trim();
    match (name.is_empty(), reason.is_empty()) {
        (_, true) => name.to_string(),
        (true, false) => reason.to_string(),
        (false, false) => format!("{}: {}", name, reason),
    }
}

fn show(_app: &AppHandle, title: &str, body: &str, _deeplink: Deeplink) {
    remember_for_activation(&_deeplink, window_focused(_app), Instant::now());
    #[cfg(all(debug_assertions, target_os = "macos"))]
    {
        // `tauri dev` runs unsigned; macOS Notification Center blocks the plugin silently. Fall back to osascript which uses the system Script Editor identity — no signing or permission grant needed for verification.
        let _ = show_via_osascript(title, body);
    }
    #[cfg(not(all(debug_assertions, target_os = "macos")))]
    {
        let _ = _app
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

// !is_active_connection: frame is from a background daemon, so focus/active-view suppression never applies — always surface.
pub fn dispatch_daemon_frame(
    app: &AppHandle,
    connection_id: &str,
    is_active_connection: bool,
    frame: &serde_json::Value,
) {
    let event = frame.get("event").and_then(|v| v.as_str()).unwrap_or("");
    let data = frame
        .get("data")
        .cloned()
        .unwrap_or(serde_json::Value::Null);
    match event {
        "approval.request" => {
            // Skip native banner when window focused — App.jsx's ApprovalSheet modal already pops, banner would be a duplicate.
            if (is_active_connection && window_focused(app)) || (!is_active_connection && request_expired(&data, now_secs())) {
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
                    connection_id: connection_id.to_string(),
                },
            );
        }
        "clarification.request" => {
            // Same rule as approvals: the ClarificationSheet already pops in a focused window on the active connection.
            if (is_active_connection && window_focused(app)) || (!is_active_connection && request_expired(&data, now_secs())) {
                return;
            }
            let profile = data
                .get("profile")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let question = data
                .get("question")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .trim();
            let request_id = data
                .get("request_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let (title, body) = clarification_lines(&profile, question);
            show(
                app,
                &title,
                &body,
                Deeplink {
                    kind: "clarification".into(),
                    profile: Some(profile),
                    id: Some(request_id),
                    connection_id: connection_id.to_string(),
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
            if is_active_connection && window_focused(app) && is_active("workgroup", &wg_id) {
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
                    connection_id: connection_id.to_string(),
                },
            );
        }
        "schedule.failed" => {
            // schedule.done is history-only here; a job with notify:true re-emits as agent.message (handled above). Only failures wake the user from this branch.
            let profile = data
                .get("profile")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let job_id = data.get("job_id").and_then(|v| v.as_str()).unwrap_or("");
            let job_title = data.get("title").and_then(|v| v.as_str()).unwrap_or("");
            let name = if job_title.trim().is_empty() { job_id } else { job_title };
            let reason_field = data.get("body").and_then(|v| v.as_str()).unwrap_or("");
            let msg = data.get("message").and_then(|v| v.as_str()).unwrap_or("");
            let reason = if reason_field.trim().is_empty() { msg } else { reason_field };
            let title = format!("{} · schedule failed", profile);
            let body = schedule_failure_body(name, reason);
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
                    connection_id: connection_id.to_string(),
                }
            } else {
                Deeplink {
                    kind: "settings".into(),
                    profile: Some(profile),
                    id: Some("schedules".into()),
                    connection_id: connection_id.to_string(),
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
            let title = data.get("title").and_then(|v| v.as_str()).unwrap_or("");
            let summary = data.get("summary").and_then(|v| v.as_str());
            let body = data.get("body").and_then(|v| v.as_str()).unwrap_or("");
            let level = data.get("type").and_then(|v| v.as_str()).unwrap_or("info");
            let (notif_title, notif_body) = notification_lines(title, summary, body, level, &profile);
            if notif_body.is_empty() {
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
            // notify(channel=alpi) is a deliberate push — always surface, even on the active chat.
            // output_id is the v0.6.11+ path; older daemons fall back to the chat/profile deeplink.
            let deeplink = if !output_id.is_empty() {
                Deeplink {
                    kind: "output".into(),
                    profile: Some(profile),
                    id: Some(output_id),
                    connection_id: connection_id.to_string(),
                }
            } else if !session_id.is_empty() {
                Deeplink {
                    kind: "chat".into(),
                    profile: Some(profile),
                    id: Some(session_id),
                    connection_id: connection_id.to_string(),
                }
            } else {
                Deeplink {
                    kind: "profile".into(),
                    profile: Some(profile),
                    id: None,
                    connection_id: connection_id.to_string(),
                }
            };
            show(app, &notif_title, &notif_body, deeplink);
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
                    connection_id: connection_id.to_string(),
                },
            );
        }
        _ => {}
    }
}

pub fn dispatch_session_done(
    app: &AppHandle,
    connection_id: &str,
    profile: &str,
    session_id: &str,
) {
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
            connection_id: connection_id.to_string(),
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
            connection_id: connection_id.to_string(),
        },
    );
}

#[cfg(test)]
mod tests {
    use super::{clarification_lines, notification_lines, replay_expired, request_expired, schedule_failure_body, NO_PROSE};

    #[test]
    fn a_replayed_request_past_its_deadline_raises_no_banner() {
        let question = serde_json::json!({"event": "clarification.request", "data": {"ts": 1000.0, "timeout_s": 300}});
        let approval = serde_json::json!({"event": "approval.request", "data": {"ts": 1000.0, "timeout_s": 60}});
        let message = serde_json::json!({"event": "agent.message", "data": {"ts": 1000.0, "timeout_s": 60}});
        assert!(replay_expired(&question, 1400.0));
        assert!(!replay_expired(&question, 1200.0));
        assert!(replay_expired(&approval, 1100.0));
        assert!(!replay_expired(&message, 99999.0));
    }

    #[test]
    fn a_request_past_its_deadline_raises_no_banner() {
        let data = serde_json::json!({"ts": 1000.0, "timeout_s": 300});
        assert!(!request_expired(&data, 1299.0));
        assert!(request_expired(&data, 1301.0));
        assert!(!request_expired(&serde_json::json!({"ts": 1000.0}), 99999.0));
        assert!(!request_expired(&serde_json::json!({}), 99999.0));
    }

    #[test]
    fn a_question_names_its_profile_and_shows_the_question() {
        assert_eq!(
            clarification_lines("doc", "Which branch?"),
            ("doc · question".to_string(), "Which branch?".to_string()),
        );
        assert_eq!(
            clarification_lines("", ""),
            ("question".to_string(), "Your agent is waiting for an answer.".to_string()),
        );
    }

    #[test]
    fn banner_leads_with_handle_and_title_over_the_summary() {
        assert_eq!(
            notification_lines("Sync failed", Some("Exit 1 after 3 retries."), "## Detail\n- trace", "info", "doc"),
            ("@doc · Sync failed".to_string(), "Exit 1 after 3 retries.".to_string()),
        );
    }

    #[test]
    fn banner_falls_back_to_the_body_for_an_older_daemon() {
        assert_eq!(
            notification_lines("Sync failed", None, "  details  ", "info", "doc"),
            ("@doc · Sync failed".to_string(), "details".to_string()),
        );
        assert_eq!(
            notification_lines("## **Alert**", None, "```text\ntrace\n```\n> **Three** replies `wait`", "info", "doc"),
            ("@doc · Alert".to_string(), "Three replies wait".to_string()),
        );
        assert_eq!(notification_lines("T", None, "| a |\n|---|", "info", "doc").1, NO_PROSE.to_string());
    }

    #[test]
    fn a_hash_or_sign_that_is_not_markup_stays() {
        assert_eq!(notification_lines("#482 needs your review", Some("s"), "b", "info", "sentinel").0, "@sentinel · #482 needs your review".to_string());
        assert_eq!(notification_lines("Fix __init__ and **kwargs**", Some("s"), "b", "info", "p").0, "@p · Fix __init__ and **kwargs**".to_string());
        assert_eq!(notification_lines("T", None, "-9% chats today", "info", "p").1, "-9% chats today".to_string());
        assert_eq!(notification_lines("T", None, "- *really* done", "info", "p").1, "*really* done".to_string());
    }

    #[test]
    fn an_older_daemon_banner_skips_headings_for_the_first_prose_line() {
        assert_eq!(notification_lines("T", None, "## Volume\nTraffic fell 9% today.", "info", "p").1, "Traffic fell 9% today.".to_string());
        assert_eq!(notification_lines("T", None, "## Only a heading", "info", "p").1, "Only a heading".to_string());
    }

    #[test]
    fn a_body_without_prose_reads_as_open_it_never_as_markdown() {
        assert_eq!(notification_lines("T", Some(""), "```\ncode\n```", "info", "doc").1, NO_PROSE.to_string());
        assert_eq!(notification_lines("T", Some(""), "```\ncode\n```", "error", "doc").1, format!("Failed · {}", NO_PROSE));
    }

    #[test]
    fn untitled_banner_is_the_handle_alone() {
        assert_eq!(
            notification_lines("doc", Some("summary"), "body", "info", "doc"),
            ("@doc".to_string(), "summary".to_string()),
        );
        assert_eq!(
            notification_lines("", Some("summary"), "body", "info", "doc"),
            ("@doc".to_string(), "summary".to_string()),
        );
    }

    #[test]
    fn default_profile_reads_as_alpi() {
        assert_eq!(
            notification_lines("Ready", Some("s"), "b", "info", "default").0,
            "@alpi · Ready".to_string(),
        );
    }

    #[test]
    fn banner_opens_with_the_level_word() {
        assert_eq!(notification_lines("T", Some("s"), "b", "warning", "p").1, "Warning · s".to_string());
        assert_eq!(notification_lines("T", Some("s"), "b", "error", "p").1, "Failed · s".to_string());
    }

    #[test]
    fn empty_summary_and_body_yield_an_empty_line() {
        assert_eq!(notification_lines("T", Some(" "), "  ", "warning", "p").1, String::new());
    }

    #[test]
    fn missing_profile_keeps_the_title_alone() {
        assert_eq!(
            notification_lines("  T  ", Some("s"), "b", "info", ""),
            ("T".to_string(), "s".to_string()),
        );
    }

    #[test]
    fn schedule_failure_uses_name_and_reason() {
        assert_eq!(
            schedule_failure_body("Monthly backlog", "agent timed out\ntimeout: timeout_1800s"),
            "Monthly backlog: agent timed out · timeout: timeout_1800s".to_string(),
        );
    }

    #[test]
    fn schedule_failure_no_name_has_no_leading_colon() {
        assert_eq!(schedule_failure_body("", "boom"), "boom".to_string());
    }

    #[test]
    fn schedule_failure_name_only() {
        assert_eq!(schedule_failure_body("weekly", ""), "weekly".to_string());
    }
}

#[cfg(test)]
mod activation_tests {
    use super::{clear_activation, remember_for_activation, take_activation, Deeplink, ACTIVATION_WINDOW};
    use std::sync::Mutex;
    use std::time::{Duration, Instant};

    static SERIAL: Mutex<()> = Mutex::new(());

    fn link(id: &str) -> Deeplink {
        Deeplink { kind: "chat".into(), profile: Some("scout".into()), id: Some(id.into()), connection_id: "local".into() }
    }

    #[test]
    fn focusing_the_window_soon_after_a_banner_opens_that_banner_once() {
        let _guard = SERIAL.lock().unwrap_or_else(|e| e.into_inner());
        let shown = Instant::now();
        remember_for_activation(&link("s1"), false, shown);
        let opened = take_activation(shown + Duration::from_secs(3)).expect("a pending activation");
        assert_eq!(opened.id.as_deref(), Some("s1"));
        assert!(take_activation(shown + Duration::from_secs(4)).is_none());
    }

    #[test]
    fn a_banner_older_than_the_window_is_not_opened() {
        let _guard = SERIAL.lock().unwrap_or_else(|e| e.into_inner());
        let shown = Instant::now();
        remember_for_activation(&link("s1"), false, shown);
        assert!(take_activation(shown + ACTIVATION_WINDOW + Duration::from_secs(1)).is_none());
    }

    #[test]
    fn a_banner_raised_while_the_window_had_focus_never_navigates() {
        let _guard = SERIAL.lock().unwrap_or_else(|e| e.into_inner());
        let shown = Instant::now();
        remember_for_activation(&link("s1"), false, shown);
        remember_for_activation(&link("s2"), true, shown);
        assert!(take_activation(shown + Duration::from_secs(1)).is_none());
    }

    #[test]
    fn only_the_latest_banner_counts() {
        let _guard = SERIAL.lock().unwrap_or_else(|e| e.into_inner());
        let shown = Instant::now();
        remember_for_activation(&link("old"), false, shown);
        remember_for_activation(&link("new"), false, shown + Duration::from_secs(1));
        assert_eq!(take_activation(shown + Duration::from_secs(2)).and_then(|d| d.id).as_deref(), Some("new"));
    }

    fn settings(id: &str) -> Deeplink {
        Deeplink { kind: "settings".into(), profile: None, id: Some(id.into()), connection_id: "local".into() }
    }

    fn request(id: &str) -> Deeplink {
        Deeplink { kind: "approval".into(), profile: Some("abby".into()), id: Some(id.into()), connection_id: "local".into() }
    }

    #[test]
    fn a_connection_or_budget_notice_never_becomes_the_place_you_land() {
        let _guard = SERIAL.lock().unwrap_or_else(|e| e.into_inner());
        let shown = Instant::now();
        clear_activation();
        remember_for_activation(&settings("connection"), false, shown);
        remember_for_activation(&settings("budget"), false, shown);
        assert!(take_activation(shown + Duration::from_secs(1)).is_none());
    }

    #[test]
    fn a_trivial_notice_does_not_replace_an_approval_waiting_on_you() {
        let _guard = SERIAL.lock().unwrap_or_else(|e| e.into_inner());
        let shown = Instant::now();
        clear_activation();
        remember_for_activation(&request("r1"), false, shown);
        remember_for_activation(&link("s9"), false, shown + Duration::from_secs(2));
        assert_eq!(take_activation(shown + Duration::from_secs(3)).and_then(|d| d.id).as_deref(), Some("r1"));
    }

    #[test]
    fn an_approval_older_than_the_window_gives_way_to_a_newer_notice() {
        let _guard = SERIAL.lock().unwrap_or_else(|e| e.into_inner());
        let shown = Instant::now();
        clear_activation();
        remember_for_activation(&request("r1"), false, shown);
        let later = shown + ACTIVATION_WINDOW + Duration::from_secs(5);
        remember_for_activation(&link("s9"), false, later);
        assert_eq!(take_activation(later + Duration::from_secs(1)).and_then(|d| d.id).as_deref(), Some("s9"));
    }

    #[test]
    fn opening_the_app_from_the_tray_or_a_shortcut_drops_the_pending_banner() {
        let _guard = SERIAL.lock().unwrap_or_else(|e| e.into_inner());
        let shown = Instant::now();
        remember_for_activation(&link("s1"), false, shown);
        clear_activation();
        assert!(take_activation(shown + Duration::from_secs(1)).is_none());
    }
}
