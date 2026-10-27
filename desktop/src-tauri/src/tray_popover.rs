use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{
    AppHandle, Emitter, LogicalSize, Manager, Monitor, Position, WebviewUrl, WebviewWindow, WebviewWindowBuilder,
    WindowEvent,
};

pub const LABEL: &str = "tray";
const WIDTH: f64 = 342.0;
const INITIAL_HEIGHT: f64 = 120.0;
const MIN_HEIGHT: f64 = 48.0;
const MAX_HEIGHT: f64 = 640.0;
const MAX_FIELD_CHARS: usize = 128;
const GAP: f64 = 14.0;
const REOPEN_GUARD: Duration = Duration::from_millis(250);
const DEEPLINK_KINDS: [&str; 2] = ["approval", "clarification"];

static ANCHOR: Mutex<Option<(f64, f64)>> = Mutex::new(None);
static PENDING: Mutex<Option<ClickAction>> = Mutex::new(None);
static HIDDEN_AT: Mutex<Option<Instant>> = Mutex::new(None);

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ScreenRect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ClickAction {
    Show,
    Hide,
    Ignore,
}

#[derive(Deserialize)]
pub struct DeeplinkArg {
    kind: String,
    profile: Option<String>,
    id: Option<String>,
    connection_id: Option<String>,
}

pub fn popover_origin(click: (f64, f64), popover: (f64, f64), work: ScreenRect, scale: f64) -> (f64, f64) {
    let fit = |value: f64, start: f64, length: f64, size: f64| value.min(start + length - size).max(start);
    let (width, height) = (popover.0.ceil(), popover.1.ceil());
    let gap = GAP * scale;
    let y = if click.1 > work.y + work.height / 2.0 { click.1 - gap - height } else { click.1 + gap };
    (
        fit(click.0 - width / 2.0, work.x, work.width, width).round(),
        fit(y, work.y, work.height, height).round(),
    )
}

pub fn scaled(rect: ScreenRect, factor: f64) -> ScreenRect {
    ScreenRect { x: rect.x * factor, y: rect.y * factor, width: rect.width * factor, height: rect.height * factor }
}

pub fn monitor_under(point: (f64, f64), bounds: &[ScreenRect]) -> Option<usize> {
    bounds
        .iter()
        .position(|r| point.0 >= r.x && point.0 < r.x + r.width && point.1 >= r.y && point.1 < r.y + r.height)
}

pub fn popover_target(point: (f64, f64), space: f64, scale: f64, work: ScreenRect, popover: (f64, f64)) -> (f64, f64) {
    let origin = popover_origin((point.0 / space, point.1 / space), (popover.0 * scale, popover.1 * scale), work, scale);
    (origin.0 * space, origin.1 * space)
}

pub fn click_action(visible: bool, since_hidden: Option<Duration>) -> ClickAction {
    if visible {
        return ClickAction::Hide;
    }
    match since_hidden {
        Some(elapsed) if elapsed < REOPEN_GUARD => ClickAction::Ignore,
        _ => ClickAction::Show,
    }
}

pub fn release_action(decided_at_press: Option<ClickAction>, decided_now: ClickAction) -> ClickAction {
    decided_at_press.unwrap_or(decided_now)
}

pub fn clamp_height(height: f64) -> Option<f64> {
    height.is_finite().then(|| height.clamp(MIN_HEIGHT, MAX_HEIGHT).ceil())
}

fn deeplink_field_ok(value: &str) -> bool {
    value.chars().count() <= MAX_FIELD_CHARS && !value.chars().any(char::is_control)
}

pub fn deeplink_payload(arg: Option<DeeplinkArg>) -> Option<Value> {
    let arg = arg?;
    let id = arg.id.filter(|id| !id.is_empty())?;
    if !DEEPLINK_KINDS.contains(&arg.kind.as_str()) {
        return None;
    }
    let fields = [Some(id.as_str()), arg.profile.as_deref(), arg.connection_id.as_deref()];
    if !fields.into_iter().flatten().all(deeplink_field_ok) {
        return None;
    }
    Some(json!({
        "deeplink": {
            "kind": arg.kind,
            "profile": arg.profile,
            "id": id,
            "connection_id": arg.connection_id.unwrap_or_default(),
        }
    }))
}

fn space_of(monitor: &Monitor) -> f64 {
    if cfg!(target_os = "macos") {
        1.0 / monitor.scale_factor()
    } else {
        1.0
    }
}

fn click_point(w: &WebviewWindow, click: (f64, f64)) -> (f64, f64) {
    #[cfg(target_os = "macos")]
    {
        let primary = w.primary_monitor().ok().flatten().map(|m| m.scale_factor()).unwrap_or(1.0);
        let cursor = w.cursor_position().map(|p| (p.x, p.y)).unwrap_or(click);
        (cursor.0 / primary, cursor.1 / primary)
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = w;
        click
    }
}

fn place(w: &WebviewWindow, point: (f64, f64), size: LogicalSize<f64>) -> Result<(), String> {
    let monitors = w.available_monitors().map_err(|e| e.to_string())?;
    let bounds: Vec<ScreenRect> = monitors
        .iter()
        .map(|m| {
            scaled(
                ScreenRect {
                    x: m.position().x as f64,
                    y: m.position().y as f64,
                    width: m.size().width as f64,
                    height: m.size().height as f64,
                },
                space_of(m),
            )
        })
        .collect();
    let monitor = match monitor_under(point, &bounds).and_then(|i| monitors.into_iter().nth(i)) {
        Some(m) => m,
        None => w.primary_monitor().map_err(|e| e.to_string())?.ok_or("No monitor for the tray popover")?,
    };
    let area = monitor.work_area();
    let work = ScreenRect {
        x: area.position.x as f64,
        y: area.position.y as f64,
        width: area.size.width as f64,
        height: area.size.height as f64,
    };
    let (x, y) = popover_target(point, space_of(&monitor), monitor.scale_factor(), work, (size.width, size.height));
    #[cfg(target_os = "macos")]
    let position = Position::Logical(tauri::LogicalPosition::new(x, y));
    #[cfg(not(target_os = "macos"))]
    let position = Position::Physical(tauri::PhysicalPosition::new(x as i32, y as i32));
    w.set_position(position).map_err(|e| e.to_string())
}

fn show_at(w: &WebviewWindow, click: (f64, f64)) {
    let factor = w.scale_factor().unwrap_or(1.0);
    let size = w
        .outer_size()
        .map(|s| LogicalSize::new(s.width as f64 / factor, s.height as f64 / factor))
        .unwrap_or(LogicalSize::new(WIDTH, INITIAL_HEIGHT));
    let point = click_point(w, click);
    if let Ok(mut anchor) = ANCHOR.lock() {
        *anchor = Some(point);
    }
    let _ = place(w, point, size);
    let _ = w.show();
    let _ = place(w, point, size);
    let _ = w.set_focus();
    let _ = w.app_handle().emit_to(LABEL, "tray-shown", ());
}

fn decide_now(app: &AppHandle) -> ClickAction {
    let visible = app.get_webview_window(LABEL).and_then(|w| w.is_visible().ok()).unwrap_or(false);
    let since_hidden = HIDDEN_AT.lock().ok().and_then(|at| at.map(|t| t.elapsed()));
    click_action(visible, since_hidden)
}

pub fn on_tray_down(app: &AppHandle) {
    let action = decide_now(app);
    if let Ok(mut pending) = PENDING.lock() {
        *pending = Some(action);
    }
}

pub fn on_tray_up(app: &AppHandle, position: (f64, f64)) {
    let Some(w) = app.get_webview_window(LABEL) else { return };
    let pending = PENDING.lock().ok().and_then(|mut p| p.take());
    match release_action(pending, decide_now(app)) {
        ClickAction::Hide => hide_popover(app),
        ClickAction::Show => show_at(&w, position),
        ClickAction::Ignore => {}
    }
}

pub fn hide_popover(app: &AppHandle) {
    if let Some(w) = app.get_webview_window(LABEL) {
        if w.is_visible().unwrap_or(false) {
            if let Ok(mut at) = HIDDEN_AT.lock() {
                *at = Some(Instant::now());
            }
        }
        let _ = w.hide();
    }
}

pub fn on_window_event(window: &tauri::Window, event: &WindowEvent) {
    match event {
        WindowEvent::Focused(false) => hide_popover(window.app_handle()),
        WindowEvent::CloseRequested { api, .. } => {
            api.prevent_close();
            hide_popover(window.app_handle());
        }
        _ => {}
    }
}

pub fn create(app: &tauri::App) -> tauri::Result<()> {
    WebviewWindowBuilder::new(app, LABEL, WebviewUrl::App("tray.html".into()))
        .title("Alpi")
        .inner_size(WIDTH, INITIAL_HEIGHT)
        .transparent(true)
        .decorations(false)
        .shadow(false)
        .resizable(false)
        .visible(false)
        .focused(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .visible_on_all_workspaces(true)
        .accept_first_mouse(true)
        .build()?;
    Ok(())
}

#[tauri::command]
pub fn resize_tray(app: AppHandle, height: f64) -> Result<(), String> {
    let height = clamp_height(height).ok_or("Invalid tray height")?;
    let Some(w) = app.get_webview_window(LABEL) else { return Ok(()) };
    let size = LogicalSize::new(WIDTH, height);
    let anchor = ANCHOR.lock().ok().and_then(|a| *a).filter(|_| w.is_visible().unwrap_or(false));
    let replace = |point: (f64, f64)| {
        if let Err(error) = place(&w, point, size) {
            eprintln!("Unable to place the tray popover: {error}");
        }
    };
    if cfg!(target_os = "macos") {
        w.set_size(size).map_err(|e| e.to_string())?;
        if let Some(point) = anchor {
            replace(point);
        }
    } else {
        if let Some(point) = anchor {
            replace(point);
        }
        w.set_size(size).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn hide_tray(app: AppHandle) {
    hide_popover(&app);
}

#[tauri::command]
pub fn tray_state() -> Option<Value> {
    crate::tray::latest_snapshot()
}

#[tauri::command]
pub fn tray_announce_state(app: AppHandle, snapshot: Value) -> Result<(), String> {
    crate::tray::announce_state(&app, snapshot)
}

#[tauri::command]
pub fn show_main(app: AppHandle, deeplink: Option<DeeplinkArg>) {
    let payload = deeplink_payload(deeplink);
    let window = crate::show_main_window(&app);
    if let (Some(window), Some(payload)) = (window, payload) {
        let _ = window.emit("notification-activated", payload);
    }
}

#[tauri::command]
pub fn open_settings(app: AppHandle) {
    if let Some(window) = crate::show_main_window(&app) {
        let _ = window.emit("nav", "settings");
    }
}

#[tauri::command]
pub fn open_notifications(app: AppHandle) {
    crate::show_main_window(&app);
    let _ = app.emit("tray:notifications-clicked", ());
}

#[tauri::command]
pub fn restart_to_update(app: AppHandle) {
    hide_popover(&app);
    let _ = app.emit("tray:update-clicked", ());
}

#[tauri::command]
pub fn quit_app(app: AppHandle) {
    app.exit(0);
}

#[tauri::command]
pub async fn start_alpi() -> Result<String, String> {
    let started = crate::off_main(crate::start_local_daemon).await?;
    crate::spawn_background("probe-after-tray-start", crate::host_client::probe_active);
    started
}

#[cfg(test)]
mod tests {
    use super::*;

    const W: f64 = 342.0;

    fn rect(x: f64, y: f64, width: f64, height: f64) -> ScreenRect {
        ScreenRect { x, y, width, height }
    }

    #[test]
    fn a_menu_bar_click_opens_the_popover_just_under_the_work_area_top() {
        let work = rect(0.0, 25.0, 1728.0, 1067.0);
        assert_eq!(popover_origin((1500.0, 12.0), (W, 200.0), work, 1.0), (1329.0, 26.0));
        assert_eq!(popover_origin((1500.0, 4.0), (W, 200.0), work, 1.0), (1329.0, 25.0));
    }

    #[test]
    fn a_bottom_taskbar_click_opens_the_popover_above_the_click() {
        let work = rect(0.0, 0.0, 1920.0, 1040.0);
        assert_eq!(popover_origin((1860.0, 1060.0), (W, 200.0), work, 1.0), (1578.0, 840.0));
    }

    #[test]
    fn a_side_taskbar_keeps_the_popover_inside_the_work_area() {
        let left = rect(48.0, 0.0, 1872.0, 1080.0);
        assert_eq!(popover_origin((20.0, 500.0), (W, 200.0), left, 1.0), (48.0, 514.0));
        let right = rect(0.0, 0.0, 1872.0, 1080.0);
        assert_eq!(popover_origin((1900.0, 1000.0), (W, 200.0), right, 1.0), (1530.0, 786.0));
    }

    #[test]
    fn the_popover_never_leaves_the_work_area_at_any_edge() {
        let work = rect(100.0, 30.0, 800.0, 600.0);
        for x in [100.0, 101.0, 500.0, 899.0, 900.0, 5000.0, -50.0] {
            for y in [30.0, 40.0, 330.0, 331.0, 629.0, 900.0] {
                let (ox, oy) = popover_origin((x, y), (W, 300.0), work, 1.0);
                assert!(ox >= work.x && ox + W <= work.x + work.width, "x {ox} for click {x},{y}");
                assert!(oy >= work.y && oy + 300.0 <= work.y + work.height, "y {oy} for click {x},{y}");
            }
        }
    }

    #[test]
    fn a_taller_popover_than_the_work_area_pins_to_the_top() {
        let work = rect(0.0, 25.0, 1000.0, 200.0);
        assert_eq!(popover_origin((500.0, 10.0), (W, 400.0), work, 1.0).1, 25.0);
    }

    #[test]
    fn the_gap_below_the_click_scales_with_the_monitor() {
        let work = rect(0.0, 0.0, 3000.0, 2000.0);
        assert_eq!(popover_origin((1500.0, 20.0), (W * 2.0, 400.0), work, 2.0).1, 48.0);
        assert_eq!(popover_origin((1500.0, 20.0), (W, 200.0), work, 1.0).1, 34.0);
        assert_eq!(popover_origin((1500.0, 1900.0), (W * 2.0, 400.0), work, 2.0).1, 1472.0);
    }

    #[test]
    fn a_fractional_size_rounds_up_so_the_edge_stays_inside() {
        let work = rect(0.0, 0.0, 1000.0, 1000.0);
        let (x, _) = popover_origin((1000.0, 10.0), (W + 0.4, 200.2), work, 1.0);
        assert_eq!(x, 1000.0 - (W + 1.0));
    }

    #[test]
    fn the_monitor_under_the_click_wins_including_negative_origins() {
        let bounds = [rect(0.0, 0.0, 1920.0, 1080.0), rect(-1440.0, -200.0, 1440.0, 900.0), rect(1920.0, 0.0, 2560.0, 1440.0)];
        assert_eq!(monitor_under((10.0, 10.0), &bounds), Some(0));
        assert_eq!(monitor_under((-5.0, 0.0), &bounds), Some(1));
        assert_eq!(monitor_under((-1440.0, -200.0), &bounds), Some(1));
        assert_eq!(monitor_under((1920.0, 0.0), &bounds), Some(2));
        assert_eq!(monitor_under((1919.9, 1079.9), &bounds), Some(0));
        assert_eq!(monitor_under((0.0, 1080.0), &bounds), None);
        assert_eq!(monitor_under((9000.0, 9000.0), &bounds), None);
    }

    #[test]
    fn a_second_monitor_places_the_popover_in_its_own_work_area() {
        let second = rect(1920.0, 0.0, 2560.0, 1400.0);
        let (x, y) = popover_origin((4400.0, 8.0), (W, 220.0), second, 1.0);
        assert_eq!((x, y), (4138.0, 22.0));
        let left = rect(-1440.0, 25.0, 1440.0, 875.0);
        let (x, y) = popover_origin((-10.0, 8.0), (W, 220.0), left, 1.0);
        assert_eq!((x, y), (-342.0, 25.0));
    }

    #[test]
    fn a_retina_point_space_maps_back_to_the_monitor_origin_units() {
        let work = rect(0.0, 50.0, 2880.0, 1750.0);
        let (x, y) = popover_target((1440.0, 8.0), 0.5, 2.0, work, (W, 200.0));
        assert_eq!((x, y), (1098.0, 25.0));
        let (x, _) = popover_target((700.0, 8.0), 0.5, 2.0, work, (W, 200.0));
        assert_eq!(x, 529.0);
    }

    #[test]
    fn a_click_closes_a_visible_popover_and_opens_a_hidden_one() {
        assert_eq!(click_action(true, None), ClickAction::Hide);
        assert_eq!(click_action(true, Some(Duration::from_millis(1))), ClickAction::Hide);
        assert_eq!(click_action(false, None), ClickAction::Show);
        assert_eq!(click_action(false, Some(Duration::from_secs(5))), ClickAction::Show);
    }

    #[test]
    fn the_click_that_blurred_the_popover_does_not_reopen_it() {
        assert_eq!(click_action(false, Some(Duration::from_millis(10))), ClickAction::Ignore);
        assert_eq!(click_action(false, Some(Duration::from_millis(249))), ClickAction::Ignore);
        assert_eq!(click_action(false, Some(Duration::from_millis(250))), ClickAction::Show);
    }

    #[test]
    fn a_long_press_that_began_on_the_blur_does_not_reopen_on_release() {
        let at_press = click_action(false, Some(Duration::from_millis(10)));
        assert_eq!(at_press, ClickAction::Ignore);
        assert_eq!(release_action(Some(at_press), ClickAction::Show), ClickAction::Ignore);
    }

    #[test]
    fn a_normal_click_toggles_from_what_the_press_saw() {
        assert_eq!(release_action(Some(click_action(false, None)), ClickAction::Hide), ClickAction::Show);
        assert_eq!(release_action(Some(click_action(true, None)), ClickAction::Show), ClickAction::Hide);
    }

    #[test]
    fn a_release_without_a_press_decides_on_the_spot() {
        assert_eq!(release_action(None, ClickAction::Show), ClickAction::Show);
        assert_eq!(release_action(None, ClickAction::Hide), ClickAction::Hide);
    }

    #[test]
    fn the_height_follows_the_content_inside_hard_limits() {
        assert_eq!(clamp_height(130.2), Some(131.0));
        assert_eq!(clamp_height(1.0), Some(MIN_HEIGHT));
        assert_eq!(clamp_height(5000.0), Some(MAX_HEIGHT));
        assert_eq!(clamp_height(f64::NAN), None);
        assert_eq!(clamp_height(f64::INFINITY), None);
    }

    fn arg(kind: &str, id: Option<&str>) -> Option<DeeplinkArg> {
        Some(DeeplinkArg {
            kind: kind.into(),
            profile: Some("abby".into()),
            id: id.map(str::to_string),
            connection_id: Some("conn-1".into()),
        })
    }

    #[test]
    fn a_review_row_emits_the_payload_shape_the_notification_listener_reads() {
        assert_eq!(
            deeplink_payload(arg("approval", Some("req-1"))),
            Some(json!({"deeplink": {"kind": "approval", "profile": "abby", "id": "req-1", "connection_id": "conn-1"}}))
        );
        assert!(deeplink_payload(arg("clarification", Some("req-2"))).is_some());
    }

    #[test]
    fn the_popover_cannot_steer_the_main_window_anywhere_else() {
        assert_eq!(deeplink_payload(None), None);
        assert_eq!(deeplink_payload(arg("approval", None)), None);
        assert_eq!(deeplink_payload(arg("approval", Some(""))), None);
        for kind in ["settings", "chat", "output", "workgroup", "profile", ""] {
            assert_eq!(deeplink_payload(arg(kind, Some("x"))), None, "{kind}");
        }
    }

    #[test]
    fn oversized_or_control_character_fields_are_refused() {
        let long = "x".repeat(129);
        let ok = "x".repeat(128);
        let make = |profile: &str, id: &str, conn: &str| {
            Some(DeeplinkArg { kind: "approval".into(), profile: Some(profile.into()), id: Some(id.into()), connection_id: Some(conn.into()) })
        };
        assert!(deeplink_payload(make(&ok, &ok, &ok)).is_some());
        assert_eq!(deeplink_payload(make(&long, "r", "c")), None);
        assert_eq!(deeplink_payload(make("p", &long, "c")), None);
        assert_eq!(deeplink_payload(make("p", "r", &long)), None);
        assert_eq!(deeplink_payload(make("p\n", "r", "c")), None);
        assert_eq!(deeplink_payload(make("p", "r\u{0}", "c")), None);
        assert_eq!(deeplink_payload(make("p", "r", "c\u{7f}")), None);
    }

    #[test]
    fn compose_and_chat_kinds_are_refused() {
        for kind in ["compose", "chat"] {
            assert_eq!(deeplink_payload(arg(kind, Some("x"))), None, "{kind}");
        }
    }

    #[test]
    fn a_missing_connection_becomes_the_empty_string_the_listener_expects() {
        let mut a = arg("approval", Some("r")).unwrap();
        a.connection_id = None;
        let payload = deeplink_payload(Some(a)).unwrap();
        assert_eq!(payload["deeplink"]["connection_id"], "");
    }
}
