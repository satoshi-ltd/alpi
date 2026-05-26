use std::sync::{Mutex, OnceLock};

use tauri::{
    image::Image,
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    App, AppHandle, Emitter, Manager,
};

const TRAY_ICON: &[u8] = include_bytes!("../icons/tray-template.png");
const TRAY_ICON_NOTIFICATION: &[u8] = include_bytes!("../icons/tray-template-notification.png");
const TOGGLE_ACCELERATOR: &str = "CmdOrCtrl+Shift+A";

#[derive(Default)]
struct TrayState {
    update_available: bool,
    update_version: Option<String>,
    window_visible: bool,
    unread_outputs: u64,
}

fn state() -> &'static Mutex<TrayState> {
    static SLOT: OnceLock<Mutex<TrayState>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(TrayState::default()))
}

fn build_menu(app: &AppHandle, s: &TrayState) -> tauri::Result<Menu<tauri::Wry>> {
    let open_label = if s.window_visible {
        "Hide Alpi"
    } else {
        "Open Alpi"
    };
    let open_item = MenuItem::with_id(
        app,
        "open",
        open_label,
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
    let snapshot = state().lock().unwrap();
    if let Ok(menu) = build_menu(app, &snapshot) {
        if let Some(tray) = app.tray_by_id("main") {
            let _ = tray.set_menu(Some(menu));
        }
    }
}

fn refresh_icon(app: &AppHandle) {
    // Template ON for both variants — macOS auto-tints to the menu bar theme. The dot ends up tinted alongside the silhouette; red emphasis lives in the Dock badge + sidebar bell.
    let needs_attention = {
        let s = state().lock().unwrap();
        s.update_available || s.unread_outputs > 0
    };
    let bytes = if needs_attention { TRAY_ICON_NOTIFICATION } else { TRAY_ICON };
    if let (Ok(icon), Some(tray)) = (Image::from_bytes(bytes), app.tray_by_id("main")) {
        let _ = tray.set_icon(Some(icon));
        let _ = tray.set_icon_as_template(true);
    }
}

pub fn install(app: &mut App) -> tauri::Result<()> {
    {
        let mut s = state().lock().unwrap();
        s.window_visible = app
            .get_webview_window("main")
            .and_then(|w| w.is_visible().ok())
            .unwrap_or(true);
    }

    let menu = build_menu(&app.handle().clone(), &state().lock().unwrap())?;
    let icon = Image::from_bytes(TRAY_ICON)?;

    TrayIconBuilder::with_id("main")
        .icon(icon)
        .icon_as_template(true)
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => {
                if let Some(window) = app.get_webview_window("main") {
                    let visible = window.is_visible().unwrap_or(false);
                    if visible {
                        let _ = window.hide();
                        set_window_visible(app, false);
                    } else {
                        let _ = window.show();
                        let _ = window.unminimize();
                        let _ = window.set_focus();
                        let _ = window.emit("nav", "home");
                        set_window_visible(app, true);
                    }
                }
            }
            "settings" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.unminimize();
                    let _ = window.set_focus();
                    let _ = window.emit("nav", "settings");
                    set_window_visible(app, true);
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
                    set_window_visible(app, true);
                }
                let _ = app.emit("tray:notifications-clicked", ());
            }
            _ => {}
        })
        .build(app)?;

    Ok(())
}

pub fn announce_update(app: &AppHandle, available: bool, version: Option<&str>) {
    {
        let mut s = state().lock().unwrap();
        let unchanged =
            s.update_available == available && s.update_version.as_deref() == version;
        if unchanged {
            return;
        }
        s.update_available = available;
        s.update_version = version.map(str::to_string);
    }
    rebuild_menu(app);
    refresh_icon(app);
}

pub fn set_window_visible(app: &AppHandle, visible: bool) {
    {
        let mut s = state().lock().unwrap();
        if s.window_visible == visible {
            return;
        }
        s.window_visible = visible;
    }
    rebuild_menu(app);
}

pub fn announce_notifications(app: &AppHandle, unread: u64) {
    {
        let mut s = state().lock().unwrap();
        if s.unread_outputs == unread {
            return;
        }
        s.unread_outputs = unread;
    }
    rebuild_menu(app);
    refresh_icon(app);
    set_dock_badge(app, unread);
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
