use std::sync::{Mutex, OnceLock};

use tauri::{
    image::Image,
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    App, AppHandle, Emitter, Manager,
};

const TRAY_ICON: &[u8] = include_bytes!("../icons/tray-template.png");
const TOGGLE_ACCELERATOR: &str = "CmdOrCtrl+Shift+A";

#[derive(Default)]
struct TrayState {
    update_available: bool,
    update_version: Option<String>,
    window_visible: bool,
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
        Menu::with_items(
            app,
            &[
                &open_item,
                &settings_item,
                &update_sep,
                &update_header,
                &update_action,
                &separator,
                &quit_item,
            ],
        )
    } else {
        Menu::with_items(app, &[&open_item, &settings_item, &separator, &quit_item])
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
