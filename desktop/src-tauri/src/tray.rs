use std::sync::{Mutex, OnceLock};

use tauri::{
    image::Image,
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    App, AppHandle, Emitter, Manager,
};

const TRAY_ICON: &[u8] = include_bytes!("../icons/tray-template.png");

#[derive(Default)]
struct UpdateState {
    available: bool,
    version: Option<String>,
}

fn state() -> &'static Mutex<UpdateState> {
    static SLOT: OnceLock<Mutex<UpdateState>> = OnceLock::new();
    SLOT.get_or_init(|| Mutex::new(UpdateState::default()))
}

fn build_menu(app: &AppHandle, update: &UpdateState) -> tauri::Result<Menu<tauri::Wry>> {
    let open_item = MenuItem::with_id(app, "open", "Open Alpi", true, None::<&str>)?;
    let settings_item =
        MenuItem::with_id(app, "settings", "Settings…", true, Some("CmdOrCtrl+,"))?;
    let separator = PredefinedMenuItem::separator(app)?;
    let quit_item = PredefinedMenuItem::quit(app, Some("Quit Alpi"))?;

    if update.available {
        let header_label = match update.version.as_deref() {
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

pub fn install(app: &mut App) -> tauri::Result<()> {
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
            _ => {}
        })
        .build(app)?;

    Ok(())
}

pub fn announce_update(app: &AppHandle, available: bool, version: Option<&str>) {
    {
        let mut s = state().lock().unwrap();
        // Skip the menu rebuild when nothing actually changed — the JS
        // poll fires periodically and we don't want to flicker the tray
        // every 6 hours.
        let unchanged = s.available == available && s.version.as_deref() == version;
        if unchanged {
            return;
        }
        s.available = available;
        s.version = version.map(str::to_string);
    }

    if let Ok(menu) = build_menu(app, &state().lock().unwrap()) {
        if let Some(tray) = app.tray_by_id("main") {
            let _ = tray.set_menu(Some(menu));
        }
    }
}
