use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex, MutexGuard, OnceLock,
};

use serde::Deserialize;
use serde_json::Value;
use tauri::{
    image::Image,
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    App, AppHandle, Emitter, Manager,
};

const SNAPSHOT_CAP_BYTES: usize = 64 * 1024;

macro_rules! tray_set {
    ($size:literal) => {
        [
            include_bytes!(concat!("../icons/tray/tray-quiet-", $size, ".png")) as &[u8],
            include_bytes!(concat!("../icons/tray/tray-dot-", $size, ".png")),
            include_bytes!(concat!("../icons/tray/tray-needs-", $size, ".png")),
            include_bytes!(concat!("../icons/tray/tray-offline-", $size, ".png")),
        ]
    };
}

const TRAY_16: [&[u8]; 4] = tray_set!("16");
const TRAY_20: [&[u8]; 4] = tray_set!("20");
const TRAY_22: [&[u8]; 4] = tray_set!("22");
const TRAY_24: [&[u8]; 4] = tray_set!("24");
const TRAY_32: [&[u8]; 4] = tray_set!("32");
const TRAY_36: [&[u8]; 4] = tray_set!("36");
const TOGGLE_ACCELERATOR: &str = "CmdOrCtrl+Shift+A";

#[derive(Default)]
struct TrayState {
    update_available: bool,
    update_version: Option<String>,
    unread_outputs: u64,
    tooltip: String,
    icon: IconState,
    snapshot: Option<Value>,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum IconState {
    #[default]
    Quiet,
    Dot,
    Needs,
    Offline,
}

#[allow(dead_code)]
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Platform {
    Mac,
    Windows,
    Linux,
}

#[cfg(target_os = "macos")]
const PLATFORM: Platform = Platform::Mac;
#[cfg(target_os = "windows")]
const PLATFORM: Platform = Platform::Windows;
#[cfg(not(any(target_os = "macos", target_os = "windows")))]
const PLATFORM: Platform = Platform::Linux;

#[derive(Deserialize, Default, Clone, PartialEq, Debug)]
pub struct Facts {
    #[serde(default)]
    state: String,
    #[serde(default)]
    counts: Counts,
    #[serde(default)]
    unread: u64,
    #[serde(default)]
    update: Option<UpdateFacts>,
}

#[derive(Deserialize, Default, Clone, PartialEq, Debug)]
struct Counts {
    #[serde(default)]
    needs: u64,
    #[serde(default)]
    failing: u64,
    #[serde(default)]
    running: u64,
}

#[derive(Deserialize, Default, Clone, PartialEq, Debug)]
struct UpdateFacts {
    #[serde(default)]
    version: Option<String>,
}

fn plural(count: u64, one: &str, many: &str) -> String {
    format!("{count} {}", if count == 1 { one } else { many })
}

pub fn tooltip_text(facts: &Facts) -> String {
    let body = match facts.state.as_str() {
        "offline" => "not running".to_string(),
        "starting" => "starting…".to_string(),
        "connecting" => "connecting…".to_string(),
        "online" if facts.update.is_none() => "online".to_string(),
        "needs" => plural(facts.counts.needs, "needs you", "need you"),
        "failing" => plural(facts.counts.failing, "job failing", "jobs failing"),
        "running" => format!("{} running", facts.counts.running),
        _ => match &facts.update {
            Some(UpdateFacts { version: Some(v) }) => format!("{v} is ready"),
            Some(_) => "an update is ready".to_string(),
            None => "all quiet".to_string(),
        },
    };
    format!("alpi · {body}")
}

pub fn icon_state(facts: &Facts) -> IconState {
    if facts.counts.needs > 0 {
        IconState::Needs
    } else if facts.state == "offline" {
        IconState::Offline
    } else if facts.update.is_some() || facts.unread > 0 {
        IconState::Dot
    } else {
        IconState::Quiet
    }
}

pub fn icon_size(platform: Platform, scale: f64) -> u32 {
    match platform {
        Platform::Mac => 36,
        Platform::Windows if scale >= 2.0 => 32,
        Platform::Windows if scale >= 1.5 => 24,
        Platform::Windows if scale >= 1.25 => 20,
        Platform::Windows => 16,
        Platform::Linux if scale > 1.0 => 24,
        Platform::Linux => 22,
    }
}

pub fn icon_bytes(state: IconState, platform: Platform, scale: f64) -> &'static [u8] {
    let set = match icon_size(platform, scale) {
        16 => &TRAY_16,
        20 => &TRAY_20,
        22 => &TRAY_22,
        24 => &TRAY_24,
        32 => &TRAY_32,
        _ => &TRAY_36,
    };
    set[state as usize]
}

type IconKey = (IconState, u32);

#[derive(Default)]
struct IconSlot {
    applied: Option<IconKey>,
    seq: u64,
}

impl IconSlot {
    fn begin(&mut self, desired: IconKey) -> Option<u64> {
        self.seq += 1;
        (self.applied != Some(desired)).then_some(self.seq)
    }

    fn finish(&mut self, seq: u64, key: IconKey, painted: bool) -> bool {
        if painted {
            self.applied = Some(key);
        }
        painted && self.seq != seq
    }
}

fn icon_slot() -> &'static Mutex<IconSlot> {
    static SLOT: OnceLock<Mutex<IconSlot>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(IconSlot::default()))
}

fn lock<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

fn display_scale(app: &AppHandle) -> f64 {
    app.get_webview_window("main")
        .and_then(|w| w.scale_factor().ok())
        .or_else(|| app.primary_monitor().ok().flatten().map(|m| m.scale_factor()))
        .unwrap_or(1.0)
}

fn state() -> &'static Mutex<TrayState> {
    static SLOT: OnceLock<Mutex<TrayState>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(TrayState::default()))
}

fn build_menu(app: &AppHandle, s: &TrayState) -> tauri::Result<Menu<tauri::Wry>> {
    let open_item = MenuItem::with_id(
        app,
        "open",
        "Open Alpi",
        true,
        Some(TOGGLE_ACCELERATOR),
    )?;
    let settings_item =
        MenuItem::with_id(app, "settings", "Settings…", true, Some("CmdOrCtrl+,"))?;
    let separator = PredefinedMenuItem::separator(app)?;
    let quit_item = PredefinedMenuItem::quit(app, Some("Quit Alpi"))?;

    let notifications_item = if s.unread_outputs > 0 {
        let label = if s.unread_outputs > 99 {
            "Notifications (99+)".to_string()
        } else {
            format!("Notifications ({})", s.unread_outputs)
        };
        Some(MenuItem::with_id(
            app,
            "notifications",
            &label,
            true,
            Some("CmdOrCtrl+O"),
        )?)
    } else {
        None
    };

    if s.update_available {
        let header_label = match s.update_version.as_deref() {
            Some(v) => format!("An update is available ({v})"),
            None => "An update is available".to_string(),
        };
        let update_header =
            MenuItem::with_id(app, "update_header", &header_label, false, None::<&str>)?;
        let update_action =
            MenuItem::with_id(app, "update", "Restart to update", true, None::<&str>)?;
        let update_sep = PredefinedMenuItem::separator(app)?;
        let mut items: Vec<&dyn tauri::menu::IsMenuItem<tauri::Wry>> =
            vec![&open_item, &settings_item];
        if let Some(ref n) = notifications_item {
            items.push(n);
        }
        items.push(&update_sep);
        items.push(&update_header);
        items.push(&update_action);
        items.push(&separator);
        items.push(&quit_item);
        Menu::with_items(app, &items)
    } else {
        let mut items: Vec<&dyn tauri::menu::IsMenuItem<tauri::Wry>> =
            vec![&open_item, &settings_item];
        if let Some(ref n) = notifications_item {
            items.push(n);
        }
        items.push(&separator);
        items.push(&quit_item);
        Menu::with_items(app, &items)
    }
}

fn rebuild_menu(app: &AppHandle) {
    let snapshot = lock(state());
    if let Ok(menu) = build_menu(app, &snapshot) {
        if let Some(tray) = app.tray_by_id("main") {
            let _ = tray.set_menu(Some(menu));
        }
    }
}

fn refresh_icon(app: &AppHandle) {
    loop {
        let scale = display_scale(app);
        let (desired, seq) = {
            let mut slot = lock(icon_slot());
            let desired = (lock(state()).icon, icon_size(PLATFORM, scale));
            match slot.begin(desired) {
                Some(seq) => (desired, seq),
                None => return,
            }
        };
        let Some(tray) = app.tray_by_id("main") else { return };
        let Ok(icon) = Image::from_bytes(icon_bytes(desired.0, PLATFORM, scale)) else { return };
        let painted = match tray.set_icon_with_as_template(Some(icon), true) {
            Ok(()) => true,
            Err(e) => {
                static LOGGED: AtomicBool = AtomicBool::new(false);
                if !LOGGED.swap(true, Ordering::Relaxed) {
                    eprintln!("tray icon update failed: {e}");
                }
                false
            }
        };
        if !lock(icon_slot()).finish(seq, desired, painted) {
            return;
        }
    }
}

pub fn install(app: &mut App) -> tauri::Result<()> {
    let menu = build_menu(&app.handle().clone(), &lock(state()))?;
    let scale = display_scale(app.handle());
    lock(icon_slot()).applied = Some((IconState::Quiet, icon_size(PLATFORM, scale)));
    let icon = Image::from_bytes(icon_bytes(IconState::Quiet, PLATFORM, scale))?;

    TrayIconBuilder::with_id("main")
        .icon(icon)
        .icon_as_template(true)
        .tooltip(tooltip_text(&Facts::default()))
        .menu(&menu)
        .show_menu_on_left_click(cfg!(target_os = "linux"))
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state, position, .. } = event {
                match button_state {
                    MouseButtonState::Down => crate::tray_popover::on_tray_down(tray.app_handle()),
                    MouseButtonState::Up => crate::tray_popover::on_tray_up(tray.app_handle(), (position.x, position.y)),
                }
            }
        })
        .on_menu_event(|app, event| {
            if matches!(event.id.as_ref(), "open" | "settings" | "notifications") {
                crate::notifications::clear_activation();
            }
            match event.id.as_ref() {
            "open" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.unminimize();
                    let _ = window.set_focus();
                    let _ = window.emit("nav", "home");
                }
            }
            "settings" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.unminimize();
                    let _ = window.set_focus();
                    let _ = window.emit("nav", "settings");
                }
            }
            "update" => {
                let _ = app.emit("tray:update-clicked", ());
            }
            "notifications" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.unminimize();
                    let _ = window.set_focus();
                }
                let _ = app.emit("tray:notifications-clicked", ());
            }
            _ => {}
            }
        })
        .build(app)?;

    Ok(())
}

pub fn within_cap(snapshot: &Value) -> bool {
    snapshot.to_string().len() <= SNAPSHOT_CAP_BYTES
}

pub fn latest_snapshot() -> Option<Value> {
    lock(state()).snapshot.clone()
}

pub fn announce_state(app: &AppHandle, snapshot: Value) -> Result<(), String> {
    if !within_cap(&snapshot) {
        return Err("Tray snapshot too large".to_string());
    }
    let facts: Facts = serde_json::from_value(snapshot.clone()).map_err(|e| e.to_string())?;
    let (menu_changed, icon_changed, tooltip_changed, unread_changed) = {
        let mut s = lock(state());
        if s.snapshot.as_ref() == Some(&snapshot) {
            return Ok(());
        }
        let available = facts.update.is_some();
        let version = facts.update.as_ref().and_then(|u| u.version.clone());
        let tooltip = tooltip_text(&facts);
        let menu_changed = s.update_available != available
            || s.update_version != version
            || s.unread_outputs != facts.unread;
        let icon = icon_state(&facts);
        let icon_changed = s.icon != icon;
        let tooltip_changed = s.tooltip != tooltip;
        let unread_changed = s.unread_outputs != facts.unread;
        s.update_available = available;
        s.update_version = version;
        s.unread_outputs = facts.unread;
        s.icon = icon;
        s.tooltip = tooltip;
        s.snapshot = Some(snapshot.clone());
        (menu_changed, icon_changed, tooltip_changed, unread_changed)
    };
    if menu_changed {
        rebuild_menu(app);
    }
    if icon_changed {
        refresh_icon(app);
    }
    if tooltip_changed {
        if let Some(tray) = app.tray_by_id("main") {
            let text = lock(state()).tooltip.clone();
            let _ = tray.set_tooltip(Some(text));
        }
    }
    if unread_changed {
        set_dock_badge(app, facts.unread);
    }
    let _ = app.emit_to(crate::tray_popover::LABEL, "tray-state", snapshot);
    Ok(())
}

#[cfg(target_os = "macos")]
fn set_dock_badge(app: &AppHandle, unread: u64) {
    let label = if unread == 0 {
        None
    } else if unread > 99 {
        Some("99+".to_string())
    } else {
        Some(unread.to_string())
    };
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_badge_label(label);
    }
}

#[cfg(not(target_os = "macos"))]
fn set_dock_badge(_app: &AppHandle, _unread: u64) {}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn facts(value: Value) -> Facts {
        serde_json::from_value(value).unwrap()
    }

    #[test]
    fn the_tooltip_names_the_heading_state() {
        let cases = [
            (json!({"state": "quiet"}), "alpi · all quiet"),
            (json!({"state": "needs", "counts": {"needs": 2}}), "alpi · 2 need you"),
            (json!({"state": "needs", "counts": {"needs": 1}}), "alpi · 1 needs you"),
            (json!({"state": "running", "counts": {"running": 2}}), "alpi · 2 running"),
            (json!({"state": "failing", "counts": {"failing": 3}}), "alpi · 3 jobs failing"),
            (json!({"state": "failing", "counts": {"failing": 1}}), "alpi · 1 job failing"),
            (json!({"state": "offline"}), "alpi · not running"),
            (json!({"state": "starting"}), "alpi · starting…"),
            (json!({"state": "connecting"}), "alpi · connecting…"),
            (json!({"state": "quiet", "update": {"version": "0.9.3"}}), "alpi · 0.9.3 is ready"),
            (json!({"state": "quiet", "update": {}}), "alpi · an update is ready"),
        ];
        for (value, expected) in cases {
            assert_eq!(tooltip_text(&facts(value.clone())), expected, "{value}");
        }
    }

    #[test]
    fn a_daemon_without_activity_reads_online_and_never_quiet() {
        assert_eq!(tooltip_text(&facts(json!({"state": "online"}))), "alpi · online");
        assert_eq!(tooltip_text(&facts(json!({"state": "online", "update": {"version": "0.9.3"}}))), "alpi · 0.9.3 is ready");
    }

    #[test]
    fn a_snapshot_over_the_cap_is_refused_and_one_at_the_cap_is_not() {
        let small = json!({"state": "quiet", "pad": "x".repeat(1000)});
        assert!(within_cap(&small));
        let huge = json!({"state": "needs", "pad": "x".repeat(SNAPSHOT_CAP_BYTES)});
        assert!(!within_cap(&huge));
        let edge = SNAPSHOT_CAP_BYTES - json!({"pad": ""}).to_string().len();
        assert!(within_cap(&json!({"pad": "x".repeat(edge)})));
        assert!(!within_cap(&json!({"pad": "x".repeat(edge + 1)})));
    }

    #[test]
    fn an_update_never_hides_what_needs_you_in_the_tooltip() {
        let both = facts(json!({"state": "needs", "counts": {"needs": 2}, "update": {"version": "0.9.3"}}));
        assert_eq!(tooltip_text(&both), "alpi · 2 need you");
    }

    #[test]
    fn an_empty_or_unknown_snapshot_reads_quiet() {
        assert_eq!(tooltip_text(&Facts::default()), "alpi · all quiet");
        assert_eq!(tooltip_text(&facts(json!({"state": "something-new"}))), "alpi · all quiet");
    }

    #[test]
    fn the_icon_state_priority_is_needs_then_offline_then_dot_then_quiet() {
        let cases = [
            (json!({"state": "quiet"}), IconState::Quiet),
            (json!({"update": {"version": "0.9.3"}}), IconState::Dot),
            (json!({"unread": 3}), IconState::Dot),
            (json!({"state": "offline"}), IconState::Offline),
            (json!({"state": "offline", "unread": 2, "update": {}}), IconState::Offline),
            (json!({"counts": {"needs": 1}}), IconState::Needs),
            (json!({"state": "offline", "counts": {"needs": 1}}), IconState::Needs),
            (json!({"counts": {"needs": 1}, "unread": 4, "update": {}}), IconState::Needs),
        ];
        for (value, expected) in cases {
            assert_eq!(icon_state(&facts(value.clone())), expected, "{value}");
        }
    }

    #[test]
    fn running_and_failing_alone_do_not_change_the_icon() {
        assert_eq!(icon_state(&facts(json!({"state": "running", "counts": {"running": 4, "failing": 2}}))), IconState::Quiet);
    }

    #[test]
    fn extra_snapshot_fields_are_ignored_by_the_daemon_side() {
        let f = facts(json!({"state": "needs", "counts": {"needs": 1}, "rows": [{"id": "x"}], "v": 1}));
        assert_eq!(f.counts.needs, 1);
    }

    #[test]
    fn the_icon_size_follows_the_platform_and_scale() {
        let cases = [
            (Platform::Mac, 1.0, 36),
            (Platform::Mac, 2.0, 36),
            (Platform::Windows, 1.0, 16),
            (Platform::Windows, 1.25, 20),
            (Platform::Windows, 1.5, 24),
            (Platform::Windows, 1.75, 24),
            (Platform::Windows, 2.0, 32),
            (Platform::Windows, 3.0, 32),
            (Platform::Linux, 1.0, 22),
            (Platform::Linux, 1.5, 24),
            (Platform::Linux, 2.0, 24),
        ];
        for (platform, scale, size) in cases {
            assert_eq!(icon_size(platform, scale), size, "{platform:?} {scale}");
        }
    }

    #[test]
    fn icon_bytes_returns_the_exact_asset_for_every_platform_scale_and_state() {
        let sets: [(Platform, f64, &[&[u8]; 4]); 10] = [
            (Platform::Mac, 1.0, &TRAY_36),
            (Platform::Mac, 2.0, &TRAY_36),
            (Platform::Windows, 1.0, &TRAY_16),
            (Platform::Windows, 1.25, &TRAY_20),
            (Platform::Windows, 1.5, &TRAY_24),
            (Platform::Windows, 2.0, &TRAY_32),
            (Platform::Windows, 3.0, &TRAY_32),
            (Platform::Linux, 1.0, &TRAY_22),
            (Platform::Linux, 1.25, &TRAY_24),
            (Platform::Linux, 2.0, &TRAY_24),
        ];
        let states = [IconState::Quiet, IconState::Dot, IconState::Needs, IconState::Offline];
        for (platform, scale, set) in sets {
            for (i, state) in states.into_iter().enumerate() {
                let bytes = icon_bytes(state, platform, scale);
                assert!(bytes == set[i], "{platform:?} {scale} {state:?}");
                let image = Image::from_bytes(bytes).unwrap();
                assert_eq!(image.width(), icon_size(platform, scale));
                assert_eq!(image.height(), icon_size(platform, scale));
            }
        }
    }

    #[test]
    fn every_state_has_its_own_bitmap() {
        for size_scale in [1.0, 1.25, 1.5, 2.0] {
            let all: Vec<&[u8]> = [IconState::Quiet, IconState::Dot, IconState::Needs, IconState::Offline]
                .into_iter()
                .map(|s| icon_bytes(s, Platform::Windows, size_scale))
                .collect();
            for a in 0..4 {
                for b in a + 1..4 {
                    assert_ne!(all[a], all[b]);
                }
            }
        }
    }

    const QUIET: IconKey = (IconState::Quiet, 36);
    const DOT: IconKey = (IconState::Dot, 36);

    #[test]
    fn refreshing_an_unchanged_icon_does_not_paint_again() {
        let mut slot = IconSlot::default();
        let seq = slot.begin(QUIET).unwrap();
        assert!(!slot.finish(seq, QUIET, true));
        assert_eq!(slot.begin(QUIET), None);
        assert!(slot.begin(DOT).is_some());
        assert_eq!(slot.begin((IconState::Dot, 24)).is_some(), true);
    }

    #[test]
    fn a_failed_paint_is_not_recorded_and_is_retried() {
        let mut slot = IconSlot::default();
        let seq = slot.begin(DOT).unwrap();
        assert!(!slot.finish(seq, DOT, false));
        assert_eq!(slot.applied, None);
        let retry = slot.begin(DOT).unwrap();
        assert!(!slot.finish(retry, DOT, true));
        assert_eq!(slot.applied, Some(DOT));
    }

    #[test]
    fn an_older_paint_finishing_after_a_newer_decision_forces_a_rerun() {
        let mut slot = IconSlot::default();
        slot.applied = Some(QUIET);
        let a = slot.begin(DOT).unwrap();
        assert_eq!(slot.begin(QUIET), None);
        assert!(slot.finish(a, DOT, true));
        assert_eq!(slot.applied, Some(DOT));
        let rerun = slot.begin(QUIET).unwrap();
        assert!(!slot.finish(rerun, QUIET, true));
        assert_eq!(slot.applied, Some(QUIET));
    }

    #[test]
    fn a_poisoned_lock_does_not_panic() {
        let m = std::sync::Arc::new(Mutex::new(5));
        let c = m.clone();
        let _ = std::thread::spawn(move || {
            let _g = c.lock().unwrap();
            panic!("poison");
        })
        .join();
        assert!(m.is_poisoned());
        assert_eq!(*lock(&m), 5);
    }

    #[test]
    fn the_tray_assets_decode() {
        for set in [&TRAY_16, &TRAY_20, &TRAY_22, &TRAY_24, &TRAY_32, &TRAY_36] {
            for bytes in set {
                assert!(Image::from_bytes(bytes).is_ok());
            }
        }
    }
}
