use std::path::{Path, PathBuf};
use std::time::Duration;

use notify::RecursiveMode;
use notify_debouncer_mini::{new_debouncer, DebounceEventResult};
use serde::Serialize;
use tauri::{AppHandle, Emitter};

use crate::home::resolve_root;

#[derive(Serialize, Clone)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum FsChange {
    Session {
        profile: String,
        session_id: String,
    },
    WorkgroupTranscript {
        profile: String,
        wg_id: String,
    },
    WorkgroupMeta {
        profile: String,
        wg_id: String,
    },
    WorkgroupMembers {
        profile: String,
        wg_id: String,
    },
    Peers {
        profile: String,
    },
    Subscriptions {
        profile: String,
    },
    Config {
        profile: String,
    },
    Other,
}

pub fn install(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let root: PathBuf = resolve_root().ok_or("could not resolve alpi root")?;
    if !root.exists() {
        std::fs::create_dir_all(&root)?;
    }
    let app = app.clone();
    let watch_root = root.clone();
    let mut debouncer = new_debouncer(
        Duration::from_millis(200),
        move |res: DebounceEventResult| {
            let Ok(events) = res else { return };
            let mut sent: std::collections::HashSet<String> = std::collections::HashSet::new();
            for ev in events {
                let change = classify(&watch_root, &ev.path);
                if matches!(change, FsChange::Other) {
                    continue;
                }
                let key = serde_json::to_string(&change).unwrap_or_default();
                if sent.insert(key) {
                    let _ = app.emit("fs-change", &change);
                }
            }
        },
    )?;
    debouncer.watcher().watch(&root, RecursiveMode::Recursive)?;
    std::mem::forget(debouncer);
    Ok(())
}

fn classify(root: &Path, path: &Path) -> FsChange {
    let Ok(rel) = path.strip_prefix(root) else {
        return FsChange::Other;
    };
    let parts: Vec<&str> = rel
        .components()
        .filter_map(|c| c.as_os_str().to_str())
        .collect();
    if parts.is_empty() {
        return FsChange::Other;
    }
    let (profile, sub): (String, &[&str]) = if parts[0] == "profiles" && parts.len() >= 2 {
        (parts[1].to_string(), &parts[2..])
    } else {
        ("default".to_string(), &parts[..])
    };
    match sub {
        ["sessions", file] => {
            let id = Path::new(file)
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("")
                .to_string();
            if id.is_empty() {
                FsChange::Other
            } else {
                FsChange::Session {
                    profile,
                    session_id: id,
                }
            }
        }
        ["alp", "workgroups", wg, "transcript.jsonl"] => FsChange::WorkgroupTranscript {
            profile,
            wg_id: (*wg).to_string(),
        },
        ["alp", "workgroups", wg, "meta.yaml"] => FsChange::WorkgroupMeta {
            profile,
            wg_id: (*wg).to_string(),
        },
        ["alp", "workgroups", wg, "members.yaml"] => FsChange::WorkgroupMembers {
            profile,
            wg_id: (*wg).to_string(),
        },
        ["alp", "peers.yaml"] => FsChange::Peers { profile },
        ["alp", "secrets", "subscriptions.yaml"] => FsChange::Subscriptions { profile },
        ["config.yaml"] => FsChange::Config { profile },
        _ => FsChange::Other,
    }
}
