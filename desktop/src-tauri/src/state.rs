use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};

use crate::home::{resolve_home, resolve_root};

const READ_MAX_BYTES: usize = 256 * 1024;
const SESSION_MAX_BYTES: usize = 1024 * 1024;
const FIRST_USER_MAX: usize = 140;

#[derive(Serialize)]
pub struct ServiceStatus {
    pub running: bool,
    pub pid: Option<u32>,
    pub socket_exists: bool,
    pub socket_path: String,
    pub pid_path: String,
}

#[derive(Serialize)]
pub struct ProfileEntry {
    pub name: String,
    pub home: String,
    pub is_default: bool,
}

#[derive(Serialize)]
pub struct ProfileSummary {
    pub name: String,
    pub home: String,
    pub is_default: bool,
    pub running: bool,
    pub pid: Option<u32>,
    pub installed_via: Option<String>,
    pub model: Option<String>,
    pub accent: Option<String>,
    pub bio: Option<String>,
    pub workspace: Option<String>,
    pub subsystems: Subsystems,
    pub tcp_port: Option<u32>,
    pub tcp_host: Option<String>,
    pub budget_daily_usd: Option<f64>,
    pub budget_daily_tokens: Option<u64>,
    pub budget_used_usd: f64,
    pub budget_used_tokens: u64,
    pub provider_keys: Vec<ProviderKey>,
    pub provider_ollama: Vec<OllamaProvider>,
    pub sandbox: bool,
    pub sandbox_allow_network: bool,
    pub voice_id: Option<String>,
    pub voice_autoplay: bool,
    pub mcps: Vec<McpServer>,
    pub counts: Counts,
    pub latest_session: Option<SessionPreview>,
    pub pubkey_b64: Option<String>,
    pub peers: Vec<PeerEntry>,
    pub models: Vec<String>,
}

#[derive(Serialize)]
pub struct WorkgroupMember {
    pub pubkey: String,
    pub bio: Option<String>,
    pub joined: bool,
}

pub fn list_workgroup_members(profile: &str, wg_id: &str) -> Vec<WorkgroupMember> {
    let Some(home) = resolve_home(Some(profile)) else {
        return vec![];
    };
    let members_path = home.join("alp/workgroups").join(wg_id).join("members.yaml");
    if let Ok(text) = fs::read_to_string(&members_path) {
        return parse_members_yaml(&text);
    }
    let subs_path = home.join("alp/secrets/subscriptions.yaml");
    if let Ok(text) = fs::read_to_string(&subs_path) {
        return parse_subscription_roster(&text, wg_id);
    }
    vec![]
}

fn parse_members_yaml(yaml: &str) -> Vec<WorkgroupMember> {
    let mut out = vec![];
    let mut current: Option<WorkgroupMember> = None;
    for line in yaml.lines() {
        let trimmed = line.trim_start();
        if let Some(rest) = trimmed.strip_prefix("- pubkey:") {
            if let Some(prev) = current.take() {
                out.push(prev);
            }
            current = Some(WorkgroupMember {
                pubkey: clean_value(rest.trim()),
                bio: None,
                joined: false,
            });
            continue;
        }
        if let Some(entry) = current.as_mut() {
            if let Some(rest) = trimmed.strip_prefix("bio:") {
                entry.bio = Some(clean_value(rest.trim()));
            } else if let Some(rest) = trimmed.strip_prefix("joined:") {
                entry.joined = clean_value(rest.trim()) == "true";
            }
        }
    }
    if let Some(prev) = current.take() {
        out.push(prev);
    }
    out
}

fn parse_subscription_roster(yaml: &str, want_wg_id: &str) -> Vec<WorkgroupMember> {
    let mut out = vec![];
    let mut in_target = false;
    let mut in_roster = false;
    let mut roster_indent: usize = 0;
    for raw in yaml.lines() {
        let trimmed = raw.trim_start();
        let indent = raw.len() - trimmed.len();
        if let Some(rest) = trimmed.strip_prefix("- wg_id:") {
            in_target = clean_value(rest.trim()) == want_wg_id;
            in_roster = false;
            continue;
        }
        if !in_target {
            continue;
        }
        if in_roster {
            if !trimmed.is_empty() && indent <= roster_indent {
                in_roster = false;
            } else if let Some((pk, _ts)) = trimmed.split_once(':') {
                let pk = pk.trim();
                if !pk.is_empty() {
                    out.push(WorkgroupMember {
                        pubkey: pk.to_string(),
                        bio: None,
                        joined: true,
                    });
                }
                continue;
            }
        }
        if trimmed.starts_with("roster:") {
            in_roster = true;
            roster_indent = indent;
        }
    }
    out
}

#[derive(Serialize)]
pub struct Subsystems {
    pub gateway: bool,
    pub schedule: bool,
    pub alp: bool,
    pub workgroups: bool,
}

#[derive(Serialize)]
pub struct OllamaProvider {
    pub name: String,
    pub url: String,
}

#[derive(Serialize)]
pub struct ProviderKey {
    pub env: String,
    pub preview: String,
}

#[derive(Serialize)]
pub struct McpServer {
    pub name: String,
    pub command: String,
    pub args: Vec<String>,
    pub env_keys: Vec<String>, // keys only, never values (may be secrets)
}

#[derive(Serialize)]
pub struct PeerEntry {
    pub id: String,
    pub pubkey: String,
    pub address: Option<String>,
    pub alias: Option<String>,
    pub allow: Vec<String>,
}

#[derive(Serialize)]
pub struct SessionPreview {
    pub id: String,
    pub mtime: u64,
    pub first_user: String,
}

#[derive(Serialize)]
pub struct Counts {
    pub peers: usize,
    pub workgroups: usize,
    pub sessions: usize,
    pub skills: usize,
    pub memory_bytes: u64,
}

#[derive(Serialize)]
pub struct SessionEntry {
    pub id: String,
    pub profile: String,
    pub mtime: u64,
    pub started_at: f64,
    pub first_user: String,
    pub model: Option<String>,
    pub turn_count: usize,
    pub kind: String,
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub cost_usd: f64,
    pub last_ctx_tokens: u64,
}

#[derive(Serialize)]
pub struct WorkgroupEntry {
    pub id: String,
    pub profile: String,
    pub name: Option<String>,
    pub briefing: Option<String>,
    pub paused: bool,
    pub members: usize,
    pub mtime: u64,
    pub path: String,
    pub budget_usd: Option<f64>,
    pub spent_usd: f64,
    pub is_hub: bool,
    pub hub_id: Option<String>,
}

#[derive(Serialize, Clone)]
pub struct DecryptedMessage {
    pub seq: u32,
    pub from: String,
    pub from_pubkey: String,
    pub body: String,
}

#[derive(Deserialize)]
struct SessionShape {
    #[serde(default)]
    turns: Vec<TurnShape>,
}

#[derive(Deserialize)]
struct TurnShape {
    #[serde(default)]
    user: String,
}

pub fn list_profiles() -> Vec<ProfileEntry> {
    let mut out = vec![];
    let Some(root) = resolve_root() else {
        return out;
    };
    if root.exists() {
        out.push(ProfileEntry {
            name: "default".into(),
            home: root.to_string_lossy().into_owned(),
            is_default: true,
        });
    }
    let profiles_dir = root.join("profiles");
    if let Ok(entries) = fs::read_dir(&profiles_dir) {
        let mut sub: Vec<_> = entries.flatten().collect();
        sub.sort_by_key(|e| e.path());
        for entry in sub {
            let path = entry.path();
            if !path.is_dir() {
                continue;
            }
            if let Some(name) = path.file_name().and_then(|s| s.to_str()) {
                out.push(ProfileEntry {
                    name: name.into(),
                    home: path.to_string_lossy().into_owned(),
                    is_default: false,
                });
            }
        }
    }
    out
}

pub fn list_profile_summaries() -> Vec<ProfileSummary> {
    list_profiles()
        .into_iter()
        .map(|p| {
            let home = PathBuf::from(&p.home);
            let cfg = fs::read_to_string(home.join("config.yaml")).unwrap_or_default();
            let svc = service_status(&home);
            let latest_session = latest_chat_for(&home);
            let installed_via = detect_installed_via(&p.name);
            ProfileSummary {
                name: p.name,
                home: p.home,
                is_default: p.is_default,
                running: svc.running,
                pid: svc.pid,
                installed_via,
                model: extract_top_level(&cfg, "model"),
                accent: extract_nested(&cfg, "tui", "accent"),
                bio: extract_top_level(&cfg, "public_bio"),
                workspace: extract_top_level(&cfg, "workspace"),
                subsystems: read_subsystems(&cfg),
                tcp_port: extract_nested(&cfg, "alp", "tcp_port")
                    .and_then(|s| s.parse().ok()),
                tcp_host: extract_nested(&cfg, "alp", "tcp_host"),
                budget_daily_usd: extract_nested(&cfg, "budget", "daily_usd")
                    .and_then(|s| s.parse().ok()),
                budget_daily_tokens: extract_nested(&cfg, "budget", "daily_tokens")
                    .and_then(|s| s.parse().ok()),
                budget_used_usd: {
                    let (u, _) = read_today_ledger(&home);
                    u
                },
                budget_used_tokens: {
                    let (_, t) = read_today_ledger(&home);
                    t
                },
                provider_keys: read_known_provider_keys(&home),
                provider_ollama: read_ollama_providers(&cfg),
                sandbox: read_sandbox(&cfg),
                sandbox_allow_network: read_sandbox_network(&cfg),
                voice_id: read_tools_tts_string(&cfg, "voice"),
                voice_autoplay: read_tools_tts_bool(&cfg, "autoplay"),
                mcps: read_mcp_servers(&cfg),
                counts: counts(&home),
                latest_session,
                pubkey_b64: read_profile_pubkey(&home),
                peers: read_profile_peers(&home),
                models: list_models(&cfg, &home),
            }
        })
        .collect()
}

fn latest_chat_for(home: &Path) -> Option<SessionPreview> {
    let dir = home.join("sessions");
    let entries = fs::read_dir(&dir).ok()?;
    let mut candidates: Vec<(PathBuf, u64)> = entries
        .flatten()
        .filter_map(|e| {
            let path = e.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                return None;
            }
            let mtime = e
                .metadata()
                .ok()
                .and_then(|m| m.modified().ok())
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs())
                .unwrap_or(0);
            Some((path, mtime))
        })
        .collect();
    candidates.sort_by(|a, b| b.1.cmp(&a.1));
    for (path, mtime) in candidates {
        let bytes = fs::read(&path).ok()?;
        let slice = &bytes[..bytes.len().min(SESSION_MAX_BYTES)];
        let Some(parsed) = serde_json::from_slice::<SessionShape>(slice).ok() else {
            continue;
        };
        let raw_first = parsed.turns.first().map(|t| t.user.as_str()).unwrap_or("");
        let first = truncate(raw_first, FIRST_USER_MAX);
        if classify_session(&first) != "chat" {
            continue;
        }
        let id = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_string();
        return Some(SessionPreview {
            id,
            mtime,
            first_user: first,
        });
    }
    None
}

pub fn list_workgroups_for(profile: &str) -> Vec<WorkgroupEntry> {
    let Some(home) = resolve_home(Some(profile)) else {
        return vec![];
    };
    let mut out = vec![];

    if let Ok(entries) = fs::read_dir(home.join("alp/workgroups")) {
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_dir() {
                continue;
            }
            let id = match path.file_name().and_then(|s| s.to_str()) {
                Some(s) => s.to_string(),
                None => continue,
            };
            let meta_text = fs::read_to_string(path.join("meta.yaml")).unwrap_or_default();
            let members_text = fs::read_to_string(path.join("members.yaml")).unwrap_or_default();
            let ledger_text = fs::read_to_string(path.join("ledger.json")).unwrap_or_default();
            let spent_usd = serde_json::from_str::<serde_json::Value>(&ledger_text)
                .ok()
                .and_then(|v| v.get("usd").and_then(|x| x.as_f64()))
                .unwrap_or(0.0);
            let budget_usd = extract_nested(&meta_text, "budget", "max_usd")
                .and_then(|s| s.parse::<f64>().ok());
            // Use transcript.jsonl mtime; fall back to the directory when missing.
            let transcript_path = path.join("transcript.jsonl");
            let mtime = transcript_path
                .metadata()
                .or_else(|_| path.metadata())
                .ok()
                .and_then(|m| m.modified().ok())
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs())
                .unwrap_or(0);
            out.push(WorkgroupEntry {
                id,
                profile: profile.to_string(),
                name: extract_top_level(&meta_text, "name"),
                briefing: extract_top_level(&meta_text, "briefing"),
                paused: extract_top_level(&meta_text, "paused")
                    .map(|s| s == "true")
                    .unwrap_or(false),
                members: members_text.lines().filter(|l| l.starts_with("- pubkey:")).count(),
                mtime,
                path: path.to_string_lossy().into_owned(),
                budget_usd,
                spent_usd,
                is_hub: true,
                hub_id: Some(profile.to_string()),
            });
        }
    }

    let subs_path = home.join("alp/secrets/subscriptions.yaml");
    if let Ok(text) = fs::read_to_string(&subs_path) {
        let mtime = subs_path
            .metadata()
            .ok()
            .and_then(|m| m.modified().ok())
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0);
        for sub in parse_subscriptions(&text) {
            out.push(WorkgroupEntry {
                id: sub.wg_id,
                profile: profile.to_string(),
                name: sub.name,
                briefing: sub.briefing,
                paused: false,
                members: sub.member_count,
                mtime,
                path: subs_path.to_string_lossy().into_owned(),
                budget_usd: None,
                spent_usd: 0.0,
                is_hub: false,
                hub_id: sub.hub_id,
            });
        }
    }

    out.sort_by(|a, b| b.mtime.cmp(&a.mtime));
    out
}

struct SubscriptionEntry {
    wg_id: String,
    name: Option<String>,
    briefing: Option<String>,
    hub_id: Option<String>,
    member_count: usize,
}

fn parse_subscriptions(yaml: &str) -> Vec<SubscriptionEntry> {
    let mut out: Vec<SubscriptionEntry> = vec![];
    let mut current: Option<SubscriptionEntry> = None;
    let mut in_roster = false;
    let mut roster_indent: usize = 0;

    for raw in yaml.lines() {
        let trimmed = raw.trim_start();
        let indent = raw.len() - trimmed.len();

        if let Some(rest) = trimmed.strip_prefix("- wg_id:") {
            if let Some(prev) = current.take() {
                out.push(prev);
            }
            current = Some(SubscriptionEntry {
                wg_id: clean_value(rest.trim()),
                name: None,
                briefing: None,
                hub_id: None,
                member_count: 0,
            });
            in_roster = false;
            continue;
        }

        let Some(entry) = current.as_mut() else { continue };

        if in_roster {
            if !trimmed.is_empty() && indent <= roster_indent && !trimmed.starts_with('-') {
                in_roster = false;
            } else if indent > roster_indent && !trimmed.is_empty() {
                entry.member_count += 1;
                continue;
            }
        }

        if let Some(rest) = trimmed.strip_prefix("name:") {
            entry.name = Some(clean_value(rest.trim()));
        } else if let Some(rest) = trimmed.strip_prefix("hub_id:") {
            entry.hub_id = Some(clean_value(rest.trim()));
        } else if let Some(rest) = trimmed.strip_prefix("briefing:") {
            entry.briefing = Some(clean_value(rest.trim()));
        } else if trimmed.starts_with("roster:") {
            in_roster = true;
            roster_indent = indent;
        }
    }
    if let Some(prev) = current.take() {
        out.push(prev);
    }
    out
}

pub fn list_workgroups_all() -> Vec<WorkgroupEntry> {
    let mut by_id: std::collections::HashMap<String, WorkgroupEntry> =
        std::collections::HashMap::new();
    for p in list_profiles() {
        for wg in list_workgroups_for(&p.name) {
            match by_id.get(&wg.id) {
                Some(existing) if existing.is_hub => continue,
                _ => {
                    by_id.insert(wg.id.clone(), wg);
                }
            }
        }
    }
    let mut out: Vec<WorkgroupEntry> = by_id.into_values().collect();
    out.sort_by(|a, b| b.mtime.cmp(&a.mtime));
    out
}

pub fn read_file_in_home(profile: Option<&str>, rel_path: &str) -> Result<String, String> {
    let home = resolve_home(profile).ok_or_else(|| "cannot resolve home".to_string())?;
    let abs = home.join(rel_path);
    let canonical = abs.canonicalize().map_err(|e| format!("{e}"))?;
    if !canonical.starts_with(&home) {
        return Err("path escapes home".into());
    }
    read_capped(&canonical).ok_or_else(|| "not readable".into())
}

fn read_subsystems(cfg: &str) -> Subsystems {
    fn parse(cfg: &str, key: &str) -> bool {
        match extract_nested(cfg, "service", key).as_deref() {
            Some("false") | Some("False") | Some("no") | Some("0") => false,
            _ => true,
        }
    }
    Subsystems {
        gateway: parse(cfg, "gateway"),
        schedule: parse(cfg, "schedule"),
        alp: parse(cfg, "alp"),
        workgroups: parse(cfg, "workgroups"),
    }
}

fn detect_installed_via(_profile: &str) -> Option<String> {
    // Single plist / unit per machine (the central alpi daemon
    // supervises every profile). The ``profile`` arg is kept for
    // call-site stability but ignored — install state is global.
    let home_dir = std::env::var_os("HOME").map(PathBuf::from)?;
    if cfg!(target_os = "macos") {
        let plist = home_dir
            .join("Library")
            .join("LaunchAgents")
            .join("com.alpi.daemon.plist");
        if plist.exists() {
            return Some("launchd".into());
        }
    } else if cfg!(target_os = "linux") {
        let unit = home_dir
            .join(".config/systemd/user")
            .join("alpi-daemon.service");
        if unit.exists() {
            return Some("systemd".into());
        }
    }
    None
}

fn service_status(home: &Path) -> ServiceStatus {
    // The central alpi daemon supervises every profile under
    // ``~/.alpi`` from a single PID file at ``<root>/service.pid``.
    // For per-profile reporting we expose that same PID + the
    // profile-local ALP socket (which only exists when the daemon
    // booted the ``alp`` subsystem for this profile).
    let root = central_root();
    let pid_path = root.join("service.pid");
    let socket_path = home.join("alp/alp.sock");
    let pid = fs::read_to_string(&pid_path)
        .ok()
        .and_then(|s| s.trim().parse::<u32>().ok());
    let running = pid.map(pid_alive).unwrap_or(false);
    ServiceStatus {
        running,
        pid,
        socket_exists: socket_path.exists(),
        socket_path: socket_path.to_string_lossy().into_owned(),
        pid_path: pid_path.to_string_lossy().into_owned(),
    }
}


fn central_root() -> PathBuf {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .map(|h| h.join(".alpi"))
        .unwrap_or_else(|| PathBuf::from(".alpi"))
}

fn pid_alive(pid: u32) -> bool {
    Command::new("kill")
        .args(["-0", &pid.to_string()])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn counts(home: &Path) -> Counts {
    Counts {
        peers: count_yaml_entries(&home.join("alp/peers.yaml")),
        workgroups: count_subdirs(&home.join("alp/workgroups")),
        sessions: count_dir_entries(&home.join("sessions"), Some("json")),
        skills: count_dir_entries(&home.join("skills"), None),
        memory_bytes: dir_size(&home.join("memories")),
    }
}

fn count_subdirs(dir: &Path) -> usize {
    let Ok(entries) = fs::read_dir(dir) else {
        return 0;
    };
    entries
        .flatten()
        .filter(|e| e.path().is_dir())
        .count()
}

fn count_yaml_entries(path: &Path) -> usize {
    let Ok(text) = fs::read_to_string(path) else {
        return 0;
    };
    text.lines()
        .filter(|l| l.starts_with("- id:") || l.starts_with("- id "))
        .count()
}

fn count_dir_entries(dir: &Path, ext: Option<&str>) -> usize {
    let Ok(entries) = fs::read_dir(dir) else {
        return 0;
    };
    entries
        .flatten()
        .filter(|e| match ext {
            None => e.path().is_dir() || e.path().is_file(),
            Some(want) => e
                .path()
                .extension()
                .and_then(|x| x.to_str())
                .map(|x| x.eq_ignore_ascii_case(want))
                .unwrap_or(false),
        })
        .count()
}

fn dir_size(dir: &Path) -> u64 {
    let mut total = 0u64;
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            if let Ok(meta) = entry.metadata() {
                if meta.is_file() {
                    total += meta.len();
                }
            }
        }
    }
    total
}

fn dir_stats_recursive(dir: &Path) -> (u64, usize) {
    let mut size = 0u64;
    let mut count = 0usize;
    let Ok(entries) = fs::read_dir(dir) else {
        return (0, 0);
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if let Ok(meta) = entry.metadata() {
            if meta.is_file() {
                size += meta.len();
                count += 1;
            } else if meta.is_dir() {
                let (s, c) = dir_stats_recursive(&path);
                size += s;
                count += c;
            }
        }
    }
    (size, count)
}

#[derive(Serialize)]
pub struct StorageEntry {
    pub key: String,
    pub label: String,
    pub path: String,
    pub size_bytes: u64,
    pub file_count: usize,
}

pub fn profile_storage(profile: &str) -> Vec<StorageEntry> {
    let Some(home) = resolve_home(Some(profile)) else {
        return vec![];
    };
    let mut out: Vec<StorageEntry> = vec![];

    {
        let path = home.join("sessions");
        let (size, count) = dir_stats_recursive(&path);
        out.push(StorageEntry {
            key: "sessions".into(),
            label: "sessions".into(),
            path: path.to_string_lossy().into_owned(),
            size_bytes: size,
            file_count: count,
        });
    }

    {
        let tts = home.join("cache/tts");
        let inbound = home.join("cache/inbound");
        let (s1, c1) = dir_stats_recursive(&tts);
        let (s2, c2) = dir_stats_recursive(&inbound);
        out.push(StorageEntry {
            key: "audio".into(),
            label: "audio".into(),
            path: tts.to_string_lossy().into_owned(),
            size_bytes: s1 + s2,
            file_count: c1 + c2,
        });
    }

    {
        let path = home.join("logs");
        let (size, count) = dir_stats_recursive(&path);
        out.push(StorageEntry {
            key: "logs".into(),
            label: "logs".into(),
            path: path.to_string_lossy().into_owned(),
            size_bytes: size,
            file_count: count,
        });
    }

    {
        let path = home.join("schedule/output");
        let (size, count) = dir_stats_recursive(&path);
        out.push(StorageEntry {
            key: "schedule".into(),
            label: "schedule".into(),
            path: path.to_string_lossy().into_owned(),
            size_bytes: size,
            file_count: count,
        });
    }

    {
        let wg_root = home.join("alp/workgroups");
        let (mut size, mut count) = dir_stats_recursive(&wg_root);
        let turns_path = home.join("alp/turns.jsonl");
        if let Ok(meta) = fs::metadata(&turns_path) {
            if meta.is_file() {
                size += meta.len();
                count += 1;
            }
        }
        out.push(StorageEntry {
            key: "workgroups".into(),
            label: "workgroups".into(),
            path: wg_root.to_string_lossy().into_owned(),
            size_bytes: size,
            file_count: count,
        });
    }

    out
}

fn read_capped(path: &Path) -> Option<String> {
    let bytes = fs::read(path).ok()?;
    let truncated = bytes.len() > READ_MAX_BYTES;
    let slice = if truncated {
        &bytes[..READ_MAX_BYTES]
    } else {
        &bytes[..]
    };
    let mut text = String::from_utf8_lossy(slice).into_owned();
    if truncated {
        text.push_str("\n…(truncated)\n");
    }
    Some(text)
}

const CURATED_YAML: &str = include_str!("../../../alpi/providers/curated_models.yaml");

pub fn list_ollama_models_for(profile: &str) -> Vec<String> {
    let Some(home) = resolve_home(Some(profile)) else {
        return vec![];
    };
    let Ok(cfg) = fs::read_to_string(home.join("config.yaml")) else {
        return vec![];
    };
    let mut out = vec![];
    for (name, url) in extract_ollama_servers(&cfg) {
        let endpoint = format!("{}/api/tags", url.trim_end_matches('/'));
        let resp = match ureq::get(&endpoint).timeout(std::time::Duration::from_millis(1500)).call() {
            Ok(r) => r,
            Err(_) => continue,
        };
        let Ok(body): Result<serde_json::Value, _> = resp.into_json() else {
            continue;
        };
        if let Some(arr) = body.get("models").and_then(|m| m.as_array()) {
            for m in arr {
                if let Some(model_name) = m.get("name").and_then(|v| v.as_str()) {
                    out.push(format!("{name}/{model_name}"));
                }
            }
        }
    }
    out
}

fn extract_ollama_servers(yaml: &str) -> Vec<(String, String)> {
    let mut out = vec![];
    let mut in_providers = false;
    let mut in_ollama = false;
    let mut current_name: Option<String> = None;
    let mut current_url: Option<String> = None;
    for line in yaml.lines() {
        if line == "providers:" {
            in_providers = true;
            in_ollama = false;
            continue;
        }
        if in_providers && !line.starts_with(' ') && !line.is_empty() {
            in_providers = false;
            in_ollama = false;
        }
        if !in_providers {
            continue;
        }
        if line == "  ollama:" || line == "  ollama: []" {
            in_ollama = line == "  ollama:";
            continue;
        }
        if in_ollama
            && line.starts_with("  ")
            && !line.starts_with("    ")
            && !line.starts_with("  -")
        {
            in_ollama = false;
        }
        if !in_ollama {
            continue;
        }
        let trimmed = line.trim_start();
        if let Some(rest) = trimmed.strip_prefix("- name:") {
            if let (Some(n), Some(u)) = (current_name.take(), current_url.take()) {
                out.push((n, u));
            }
            current_name = Some(rest.trim().trim_matches('"').to_string());
        } else if let Some(rest) = trimmed.strip_prefix("name:") {
            current_name = Some(rest.trim().trim_matches('"').to_string());
        } else if let Some(rest) = trimmed.strip_prefix("url:") {
            current_url = Some(rest.trim().trim_matches('"').to_string());
        }
    }
    if let (Some(n), Some(u)) = (current_name, current_url) {
        out.push((n, u));
    }
    out
}

fn list_models(cfg: &str, home: &Path) -> Vec<String> {
    let mut out: Vec<String> = vec![];
    if let Some(default) = extract_top_level(cfg, "model") {
        if !default.is_empty() {
            out.push(default);
        }
    }
    let env = read_env_keys(home);
    for (provider, key_env) in [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")] {
        if !env.get(key_env).map(|v| !v.is_empty()).unwrap_or(false) {
            continue;
        }
        for id in curated_ids_for(provider) {
            out.push(format!("{provider}/{id}"));
        }
    }
    out.extend(extract_openrouter_models(cfg));
    let mut seen = std::collections::HashSet::new();
    out.retain(|m| seen.insert(m.clone()));
    out
}

fn curated_ids_for(provider: &str) -> Vec<String> {
    let mut out = vec![];
    let header = format!("{provider}:");
    let mut in_block = false;
    for line in CURATED_YAML.lines() {
        if line == header {
            in_block = true;
            continue;
        }
        if in_block && !line.starts_with(' ') && !line.is_empty() {
            break;
        }
        if !in_block {
            continue;
        }
        let trimmed = line.trim_start();
        if let Some(rest) = trimmed.strip_prefix("- id:") {
            out.push(rest.trim().trim_matches('"').to_string());
        }
    }
    out
}

fn read_env_keys(home: &Path) -> std::collections::HashMap<String, String> {
    let mut out = std::collections::HashMap::new();
    let Ok(text) = fs::read_to_string(home.join(".env")) else {
        return out;
    };
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            let v = v.trim().trim_matches('"').trim_matches('\'');
            out.insert(k.trim().to_string(), v.to_string());
        }
    }
    out
}

fn extract_openrouter_models(yaml: &str) -> Vec<String> {
    let mut out = vec![];
    let mut in_openrouter = false;
    let mut in_models = false;
    for line in yaml.lines() {
        if line == "  openrouter:" || line == "  openrouter: {}" {
            in_openrouter = line == "  openrouter:";
            in_models = false;
            continue;
        }
        if in_openrouter
            && !line.is_empty()
            && !line.starts_with("    ")
            && !line.starts_with("\t")
        {
            in_openrouter = false;
            in_models = false;
        }
        if !in_openrouter {
            continue;
        }
        let trimmed = line.trim_start();
        if trimmed == "models:" {
            in_models = true;
            continue;
        }
        if in_models {
            if let Some(rest) = trimmed.strip_prefix("- ") {
                out.push(format!("openrouter/{}", rest.trim()));
            } else if !trimmed.starts_with('-') && !trimmed.is_empty() {
                in_models = false;
            }
        }
    }
    out
}

fn read_today_ledger(home: &Path) -> (f64, u64) {
    let path = home.join("logs").join("ledger.json");
    let text = match fs::read_to_string(&path) {
        Ok(s) => s,
        Err(_) => return (0.0, 0),
    };
    let v: serde_json::Value = match serde_json::from_str(&text) {
        Ok(v) => v,
        Err(_) => return (0.0, 0),
    };
    let day = v.get("day").and_then(|x| x.as_str()).unwrap_or("");
    if day != today_utc_iso() {
        return (0.0, 0);
    }
    let prof = v.get("profile").cloned().unwrap_or_default();
    let usd = prof.get("usd").and_then(|x| x.as_f64()).unwrap_or(0.0);
    let tokens = prof.get("tokens").and_then(|x| x.as_u64()).unwrap_or(0);
    (usd, tokens)
}

fn today_utc_iso() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let days = secs / 86400;
    // Howard Hinnant's civil-from-days algorithm.
    let z = days + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = (z - era * 146097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!("{:04}-{:02}-{:02}", y, m, d)
}

const KNOWN_PROVIDER_KEYS: &[&str] = &[
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
];

fn read_known_provider_keys(home: &Path) -> Vec<ProviderKey> {
    let env = read_env_keys(home);
    let mut out = vec![];
    for k in KNOWN_PROVIDER_KEYS {
        let Some(v) = env.get(*k) else { continue };
        if v.is_empty() {
            continue;
        }
        out.push(ProviderKey {
            env: k.to_string(),
            preview: mask_key(v),
        });
    }
    out
}

fn mask_key(value: &str) -> String {
    // Show first 3 chars + last 4 chars.
    let chars: Vec<char> = value.chars().collect();
    if chars.len() <= 8 {
        return "•".repeat(chars.len());
    }
    let head: String = chars.iter().take(3).collect();
    let tail: String = chars.iter().rev().take(4).collect::<Vec<_>>().into_iter().rev().collect();
    format!("{head}…{tail}")
}

fn read_sandbox(cfg: &str) -> bool {
    read_tools_terminal_bool(cfg, "sandbox")
}

fn read_sandbox_network(cfg: &str) -> bool {
    read_tools_terminal_bool(cfg, "allow_network")
}

fn read_tools_tts_string(cfg: &str, key: &str) -> Option<String> {
    read_tools_subblock(cfg, "tts", key)
}

fn read_tools_tts_bool(cfg: &str, key: &str) -> bool {
    read_tools_subblock(cfg, "tts", key)
        .map(|v| v == "true")
        .unwrap_or(false)
}

fn read_tools_subblock(cfg: &str, sub: &str, key: &str) -> Option<String> {
    let header = format!("{sub}:");
    let mut in_tools = false;
    let mut in_sub = false;
    for raw in cfg.lines() {
        if raw.starts_with("tools:") {
            in_tools = true;
            continue;
        }
        if !in_tools {
            continue;
        }
        if !raw.starts_with(' ') && !raw.is_empty() {
            return None;
        }
        let trimmed = raw.trim_start();
        if trimmed.starts_with(&header) {
            in_sub = true;
            continue;
        }
        if !in_sub {
            continue;
        }
        if raw.starts_with("  ") && !raw.starts_with("    ") && trimmed.contains(':') {
            return None;
        }
        if let Some(rest) = trimmed.strip_prefix(&format!("{key}:")) {
            return Some(
                rest.trim()
                    .trim_matches('"')
                    .trim_matches('\'')
                    .to_string(),
            );
        }
    }
    None
}

fn read_tools_terminal_bool(cfg: &str, key: &str) -> bool {
    // Hand-rolled depth-3 reader for `tools: terminal: <key>: bool`.
    let mut in_tools = false;
    let mut in_terminal = false;
    for raw in cfg.lines() {
        if raw.starts_with("tools:") {
            in_tools = true;
            continue;
        }
        if !in_tools {
            continue;
        }
        if !raw.starts_with(' ') && !raw.is_empty() {
            in_tools = false;
            in_terminal = false;
            continue;
        }
        let trimmed = raw.trim_start();
        if trimmed.starts_with("terminal:") {
            in_terminal = true;
            continue;
        }
        if !in_terminal {
            continue;
        }
        // Exit terminal block on a sibling key.
        if raw.starts_with("  ") && !raw.starts_with("    ") && trimmed.contains(':') {
            in_terminal = false;
            continue;
        }
        if let Some(rest) = trimmed.strip_prefix(&format!("{key}:")) {
            return rest.trim() == "true";
        }
    }
    false
}

fn read_mcp_servers(cfg: &str) -> Vec<McpServer> {
    // Parse `mcp.servers` from config.yaml.
    let mut out = vec![];
    let mut in_mcp = false;
    let mut in_servers = false;
    let mut cur: Option<McpServer> = None;
    let mut in_args = false;
    let mut in_env = false;
    for raw in cfg.lines() {
        if raw.starts_with("mcp:") {
            in_mcp = true;
            continue;
        }
        if !in_mcp {
            continue;
        }
        if !raw.starts_with(' ') && !raw.is_empty() {
            break;
        }
        let trimmed = raw.trim_start();
        if trimmed.starts_with("servers:") {
            in_servers = true;
            continue;
        }
        if !in_servers {
            continue;
        }
        // Server name is at 4-space indent: "    github:".
        if raw.starts_with("    ") && !raw.starts_with("      ") {
            if let Some(srv) = cur.take() {
                out.push(srv);
            }
            in_args = false;
            in_env = false;
            if let Some(name) = trimmed.strip_suffix(':') {
                cur = Some(McpServer {
                    name: name.to_string(),
                    command: String::new(),
                    args: vec![],
                    env_keys: vec![],
                });
            }
            continue;
        }
        let Some(srv) = cur.as_mut() else { continue };
        if let Some(rest) = trimmed.strip_prefix("command:") {
            srv.command = rest.trim().trim_matches('"').trim_matches('\'').to_string();
            in_args = false;
            in_env = false;
        } else if trimmed.starts_with("args:") {
            in_args = true;
            in_env = false;
            // Inline `args: [a, b]` list.
            if let Some(rest) = trimmed.strip_prefix("args:") {
                let r = rest.trim();
                if r.starts_with('[') && r.ends_with(']') {
                    let inner = &r[1..r.len() - 1];
                    for tok in inner.split(',') {
                        let t = tok.trim().trim_matches('"').trim_matches('\'');
                        if !t.is_empty() {
                            srv.args.push(t.to_string());
                        }
                    }
                    in_args = false;
                }
            }
        } else if trimmed.starts_with("env:") {
            in_env = true;
            in_args = false;
        } else if in_args && trimmed.starts_with("- ") {
            let v = trimmed.trim_start_matches("- ").trim_matches('"').trim_matches('\'');
            srv.args.push(v.to_string());
        } else if in_env && trimmed.contains(':') {
            if let Some((k, _)) = trimmed.split_once(':') {
                srv.env_keys.push(k.trim().to_string());
            }
        } else {
            in_args = false;
            in_env = false;
        }
    }
    if let Some(srv) = cur {
        out.push(srv);
    }
    out
}

fn read_ollama_providers(cfg: &str) -> Vec<OllamaProvider> {
    let mut out = vec![];
    let mut in_providers = false;
    let mut in_ollama = false;
    let mut cur_name: Option<String> = None;
    let mut cur_url: Option<String> = None;
    for raw in cfg.lines() {
        if raw.starts_with("providers:") {
            in_providers = true;
            continue;
        }
        if !in_providers {
            continue;
        }
        // Exit providers block on an unindented non-empty line.
        if !raw.starts_with(' ') && !raw.is_empty() {
            in_providers = false;
            in_ollama = false;
            continue;
        }
        let trimmed = raw.trim_start();
        if trimmed.starts_with("ollama:") {
            in_ollama = true;
            continue;
        }
        if !in_ollama {
            continue;
        }
        // A new sibling under `providers:` ends ollama.
        if !raw.starts_with("    ")
            && !raw.starts_with("  -")
            && raw.starts_with("  ")
            && trimmed.contains(':')
            && !trimmed.starts_with("- ")
            && !trimmed.starts_with("name:")
            && !trimmed.starts_with("url:")
        {
            in_ollama = false;
            continue;
        }
        if let Some(rest) = trimmed.strip_prefix("- name:") {
            if let Some(name) = cur_name.take() {
                out.push(OllamaProvider {
                    name,
                    url: cur_url.take().unwrap_or_default(),
                });
            }
            cur_name = Some(rest.trim().trim_matches('"').trim_matches('\'').to_string());
        } else if let Some(rest) = trimmed.strip_prefix("name:") {
            // YAML may put name on its own line under the dash.
            cur_name = Some(rest.trim().trim_matches('"').trim_matches('\'').to_string());
        } else if let Some(rest) = trimmed.strip_prefix("url:") {
            cur_url = Some(rest.trim().trim_matches('"').trim_matches('\'').to_string());
        }
    }
    if let Some(name) = cur_name {
        out.push(OllamaProvider {
            name,
            url: cur_url.unwrap_or_default(),
        });
    }
    out
}

fn read_profile_pubkey(home: &Path) -> Option<String> {
    let pem = fs::read_to_string(home.join("alp/secrets/alp_key.pub")).ok()?;
    let inner = pem
        .lines()
        .filter(|l| !l.starts_with("-----"))
        .collect::<String>();
    let der = base64_decode(&inner)?;
    if der.len() < 32 {
        return None;
    }
    let raw = &der[der.len() - 32..];
    Some(base64_encode(raw))
}

fn read_profile_peers(home: &Path) -> Vec<PeerEntry> {
    let text = match fs::read_to_string(home.join("alp/peers.yaml")) {
        Ok(s) => s,
        Err(_) => return vec![],
    };
    let mut out = vec![];
    let mut cur: Option<PeerEntry> = None;
    let mut in_allow = false;
    for raw in text.lines() {
        if let Some(rest) = raw.strip_prefix("- id:") {
            if let Some(prev) = cur.take() {
                if !prev.pubkey.is_empty() {
                    out.push(prev);
                }
            }
            cur = Some(PeerEntry {
                id: rest.trim().to_string(),
                pubkey: String::new(),
                address: None,
                alias: None,
                allow: vec![],
            });
            in_allow = false;
        } else if let Some(p) = cur.as_mut() {
            let trimmed = raw.trim_start();
            if let Some(v) = trimmed.strip_prefix("pubkey:") {
                p.pubkey = clean_value(v);
                in_allow = false;
            } else if let Some(v) = trimmed.strip_prefix("address:") {
                let s = clean_value(v);
                if !s.is_empty() {
                    p.address = Some(s);
                }
                in_allow = false;
            } else if let Some(v) = trimmed.strip_prefix("alias:") {
                let s = clean_value(v);
                if !s.is_empty() {
                    p.alias = Some(s);
                }
                in_allow = false;
            } else if trimmed.starts_with("allow:") {
                in_allow = true;
            } else if in_allow {
                if let Some(item) = trimmed.strip_prefix("- ") {
                    let m = clean_value(item);
                    if !m.is_empty() {
                        p.allow.push(m);
                    }
                } else if !trimmed.is_empty() {
                    in_allow = false;
                }
            }
        }
    }
    if let Some(p) = cur {
        if !p.pubkey.is_empty() {
            out.push(p);
        }
    }
    out
}

fn base64_decode(input: &str) -> Option<Vec<u8>> {
    let table: [i8; 256] = build_b64_table();
    let s: Vec<u8> = input.bytes().filter(|b| !b.is_ascii_whitespace()).collect();
    let s = if s.ends_with(b"==") { &s[..s.len() - 2] }
        else if s.ends_with(b"=") { &s[..s.len() - 1] }
        else { &s[..] };
    let mut out = Vec::with_capacity(s.len() * 3 / 4);
    let mut buf: u32 = 0;
    let mut bits = 0u32;
    for b in s {
        let idx = table[*b as usize];
        if idx < 0 {
            return None;
        }
        buf = (buf << 6) | (idx as u32);
        bits += 6;
        if bits >= 8 {
            bits -= 8;
            out.push(((buf >> bits) & 0xff) as u8);
        }
    }
    Some(out)
}

fn base64_encode(input: &[u8]) -> String {
    const ALPHA: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(((input.len() + 2) / 3) * 4);
    let mut i = 0;
    while i < input.len() {
        let b0 = input[i];
        let b1 = if i + 1 < input.len() { input[i + 1] } else { 0 };
        let b2 = if i + 2 < input.len() { input[i + 2] } else { 0 };
        let n = ((b0 as u32) << 16) | ((b1 as u32) << 8) | (b2 as u32);
        out.push(ALPHA[((n >> 18) & 0x3f) as usize] as char);
        out.push(ALPHA[((n >> 12) & 0x3f) as usize] as char);
        if i + 1 < input.len() {
            out.push(ALPHA[((n >> 6) & 0x3f) as usize] as char);
        } else {
            out.push('=');
        }
        if i + 2 < input.len() {
            out.push(ALPHA[(n & 0x3f) as usize] as char);
        } else {
            out.push('=');
        }
        i += 3;
    }
    out
}

const fn build_b64_table() -> [i8; 256] {
    let mut t = [-1i8; 256];
    let alpha = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut i = 0;
    while i < alpha.len() {
        t[alpha[i] as usize] = i as i8;
        i += 1;
    }
    t
}

fn classify_session(first_user: &str) -> &'static str {
    let trimmed = first_user.trim_start();
    if trimmed.starts_with("[workgroup-poller]") || trimmed.starts_with("[workgroup ") {
        "workgroup"
    } else if trimmed.starts_with("[SCHEDULED:") || trimmed.starts_with("[CRON") {
        "scheduled"
    } else if trimmed.starts_with("[INBOUND TELEGRAM") {
        "telegram"
    } else if trimmed.starts_with("[INBOUND IMAP") || trimmed.starts_with("[INBOUND GMAIL") {
        "email"
    } else if trimmed.starts_with("[INBOUND ") {
        "gateway"
    } else if trimmed.starts_with("[") {
        "system"
    } else if trimmed.is_empty() {
        "empty"
    } else {
        "chat"
    }
}

fn truncate(s: &str, max_chars: usize) -> String {
    let mut out = String::new();
    for (i, c) in s.chars().enumerate() {
        if i >= max_chars {
            out.push('…');
            break;
        }
        if c == '\n' || c == '\r' {
            out.push(' ');
        } else {
            out.push(c);
        }
    }
    out.trim().to_string()
}

#[derive(Serialize)]
pub struct GatewayStatus {
    pub name: String,
    pub configured: bool,
}

#[derive(Serialize)]
pub struct SkillEntry {
    pub category: Option<String>,
    pub name: String,
    pub description: Option<String>,
}

fn read_skill_description(skill_md: &Path) -> Option<String> {
    let text = fs::read_to_string(skill_md).ok()?;
    let mut lines = text.lines();
    if lines.next()?.trim() != "---" {
        return None;
    }
    for line in lines {
        let line = line.trim();
        if line == "---" {
            break;
        }
        if let Some(rest) = line.strip_prefix("description:") {
            let v = rest.trim().trim_matches('"').trim_matches('\'').trim();
            if v.is_empty() {
                return None;
            }
            return Some(v.to_string());
        }
    }
    None
}

pub fn list_skills_for(profile: &str) -> Vec<SkillEntry> {
    let Some(home) = resolve_home(Some(profile)) else {
        return vec![];
    };
    let dir = home.join("skills");
    let Ok(entries) = fs::read_dir(&dir) else {
        return vec![];
    };
    let mut out: Vec<SkillEntry> = vec![];
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let Some(top_name) = entry.file_name().into_string().ok() else {
            continue;
        };
        if top_name.starts_with('.') {
            continue;
        }
        if path.join("SKILL.md").exists() {
            let description = read_skill_description(&path.join("SKILL.md"));
            out.push(SkillEntry {
                category: None,
                name: top_name,
                description,
            });
            continue;
        }
        let Ok(children) = fs::read_dir(&path) else {
            continue;
        };
        for child in children.flatten() {
            let child_path = child.path();
            if !child_path.is_dir() {
                continue;
            }
            if !child_path.join("SKILL.md").exists() {
                continue;
            }
            let Some(child_name) = child.file_name().into_string().ok() else {
                continue;
            };
            if child_name.starts_with('.') {
                continue;
            }
            let description =
                read_skill_description(&child_path.join("SKILL.md"));
            out.push(SkillEntry {
                category: Some(top_name.clone()),
                name: child_name,
                description,
            });
        }
    }
    out.sort_by(|a, b| {
        a.category
            .as_deref()
            .unwrap_or("")
            .cmp(b.category.as_deref().unwrap_or(""))
            .then(a.name.cmp(&b.name))
    });
    out
}

// Return the gateway's env-driven config so the desktop can pre-fill
// the editor. Secrets are masked; non-secret fields are cleartext.
pub fn read_gateway_config(profile: &str, name: &str) -> std::collections::HashMap<String, String> {
    let mut out = std::collections::HashMap::new();
    let Some(home) = resolve_home(Some(profile)) else {
        return out;
    };
    let env = read_env_keys(&home);
    let put_secret = |out: &mut std::collections::HashMap<String, String>, k: &str| {
        if let Some(v) = env.get(k) {
            if !v.is_empty() {
                out.insert(k.to_string(), mask_key(v));
            }
        }
    };
    let put_plain = |out: &mut std::collections::HashMap<String, String>, k: &str| {
        if let Some(v) = env.get(k) {
            if !v.is_empty() {
                out.insert(k.to_string(), v.clone());
            }
        }
    };
    match name {
        "telegram" => {
            put_secret(&mut out, "TELEGRAM_BOT_TOKEN");
            put_plain(&mut out, "TELEGRAM_ALLOWED_CHAT_IDS");
        }
        "imap" => {
            put_plain(&mut out, "IMAP_ADDRESS");
            put_secret(&mut out, "IMAP_PASSWORD");
            put_plain(&mut out, "IMAP_HOST");
            put_plain(&mut out, "IMAP_PORT");
            put_plain(&mut out, "IMAP_ALLOWED_SENDERS");
        }
        "gmail" => {
            put_plain(&mut out, "GMAIL_CLIENT_ID");
            put_secret(&mut out, "GMAIL_CLIENT_SECRET");
            put_plain(&mut out, "GMAIL_ALLOWED_SENDERS");
        }
        _ => {}
    }
    out
}

pub fn list_gateway_status(profile: &str) -> Vec<GatewayStatus> {
    let Some(home) = resolve_home(Some(profile)) else {
        return vec![];
    };
    let env = read_env_keys(&home);
    let gmail_token = home.join("secrets").join("gmail_token.json").exists();
    vec![
        GatewayStatus {
            name: "telegram".into(),
            configured: env.get("TELEGRAM_BOT_TOKEN").map_or(false, |v| !v.is_empty()),
        },
        GatewayStatus {
            name: "imap".into(),
            configured: env.get("IMAP_ADDRESS").map_or(false, |v| !v.is_empty()),
        },
        GatewayStatus {
            name: "gmail".into(),
            configured: env.get("GMAIL_CLIENT_ID").map_or(false, |v| !v.is_empty())
                || gmail_token,
        },
    ]
}

pub fn set_config_field(profile: &str, key: &str, value: &str) -> Result<(), String> {
    let home = resolve_home(Some(profile)).ok_or_else(|| "no home".to_string())?;
    let path = home.join("config.yaml");
    let text = fs::read_to_string(&path).unwrap_or_default();
    let updated = write_yaml_field(&text, key, value);
    fs::write(&path, updated).map_err(|e| format!("write config.yaml: {e}"))
}

pub fn unset_config_field(profile: &str, key: &str) -> Result<(), String> {
    let home = resolve_home(Some(profile)).ok_or_else(|| "no home".to_string())?;
    let path = home.join("config.yaml");
    let text = fs::read_to_string(&path).unwrap_or_default();
    let updated = remove_yaml_field(&text, key);
    fs::write(&path, updated).map_err(|e| format!("write config.yaml: {e}"))
}

fn remove_yaml_field(yaml: &str, dotted: &str) -> String {
    let parts: Vec<&str> = dotted.split('.').collect();
    if parts.len() == 1 {
        return remove_top(yaml, parts[0]);
    }
    if parts.len() == 2 {
        return remove_nested(yaml, parts[0], parts[1]);
    }
    yaml.to_string()
}

fn remove_top(yaml: &str, key: &str) -> String {
    let prefix = format!("{key}:");
    let mut out = String::new();
    for line in yaml.lines() {
        if line.trim_start().starts_with(&prefix) && !line.starts_with(' ') {
            continue;
        }
        out.push_str(line);
        out.push('\n');
    }
    out.trim_end().to_string() + "\n"
}

fn remove_nested(yaml: &str, parent: &str, child: &str) -> String {
    let parent_prefix = format!("{parent}:");
    let child_prefix = format!("{child}:");
    let mut out = String::new();
    let mut in_parent = false;
    let mut parent_indent = 0usize;
    let lines: Vec<&str> = yaml.lines().collect();
    let mut parent_kept_lines = String::new();
    let mut parent_header: Option<String> = None;
    let mut consumed_parent = false;
    for line in lines {
        let trimmed = line.trim_start();
        let indent = line.len() - trimmed.len();
        if !in_parent {
            if trimmed.starts_with(&parent_prefix) && !line.starts_with(' ') {
                in_parent = true;
                parent_indent = indent;
                parent_header = Some(line.to_string());
                consumed_parent = true;
                continue;
            }
            out.push_str(line);
            out.push('\n');
            continue;
        }
        if trimmed.is_empty() || indent <= parent_indent {
            if let Some(h) = parent_header.take() {
                if !parent_kept_lines.is_empty() {
                    out.push_str(&h);
                    out.push('\n');
                    out.push_str(&parent_kept_lines);
                }
            }
            in_parent = false;
            parent_kept_lines.clear();
            out.push_str(line);
            out.push('\n');
            continue;
        }
        if trimmed.starts_with(&child_prefix) {
            continue;
        }
        parent_kept_lines.push_str(line);
        parent_kept_lines.push('\n');
    }
    if consumed_parent {
        if let Some(h) = parent_header {
            if !parent_kept_lines.is_empty() {
                out.push_str(&h);
                out.push('\n');
                out.push_str(&parent_kept_lines);
            }
        }
    }
    out.trim_end().to_string() + "\n"
}

fn write_yaml_field(yaml: &str, dotted: &str, value: &str) -> String {
    let parts: Vec<&str> = dotted.split('.').collect();
    let escaped = yaml_scalar(value);
    if parts.len() == 1 {
        return replace_or_append_top(yaml, parts[0], &escaped);
    }
    if parts.len() == 2 {
        return replace_or_append_nested(yaml, parts[0], parts[1], &escaped);
    }
    yaml.to_string()
}

fn yaml_scalar(value: &str) -> String {
    if value.is_empty() {
        return "''".into();
    }
    if value.contains('\n')
        || value.contains(':')
        || value.contains('#')
        || value.starts_with(' ')
        || value.ends_with(' ')
        || value.starts_with('-')
        || value.starts_with('"')
        || value.starts_with('\'')
    {
        let escaped = value.replace('\'', "''");
        return format!("'{escaped}'");
    }
    value.to_string()
}

fn replace_or_append_top(yaml: &str, key: &str, value: &str) -> String {
    let prefix = format!("{key}:");
    let mut out = String::new();
    let mut replaced = false;
    for line in yaml.lines() {
        let trimmed = line.trim_start();
        if !replaced
            && (trimmed == prefix || trimmed.starts_with(&format!("{key}: ")))
            && !line.starts_with(' ')
        {
            out.push_str(&format!("{key}: {value}\n"));
            replaced = true;
        } else {
            out.push_str(line);
            out.push('\n');
        }
    }
    if !replaced {
        if !out.ends_with('\n') {
            out.push('\n');
        }
        out.push_str(&format!("{key}: {value}\n"));
    }
    out
}

fn replace_or_append_nested(yaml: &str, parent: &str, child: &str, value: &str) -> String {
    let parent_marker = format!("{parent}:");
    let child_prefix_a = format!("  {child}:");
    let child_prefix_b = format!("  {child}: ");
    let mut out = String::new();
    let mut in_parent = false;
    let mut replaced = false;
    let mut parent_seen = false;
    for line in yaml.lines() {
        if !line.starts_with(' ') && (line == parent_marker || line.starts_with(&format!("{parent_marker} "))) {
            in_parent = true;
            parent_seen = true;
            out.push_str(line);
            out.push('\n');
            continue;
        }
        if in_parent
            && (line.trim_start() == child_prefix_a
                || line.starts_with(&child_prefix_b)
                || line.trim_start().starts_with(&format!("{child}: ")))
        {
            out.push_str(&format!("  {child}: {value}\n"));
            replaced = true;
            in_parent = false;
            continue;
        }
        if in_parent && !line.is_empty() && !line.starts_with(' ') {
            if !replaced {
                out.push_str(&format!("  {child}: {value}\n"));
                replaced = true;
            }
            in_parent = false;
        }
        out.push_str(line);
        out.push('\n');
    }
    if !replaced {
        if !parent_seen {
            if !out.ends_with('\n') {
                out.push('\n');
            }
            out.push_str(&format!("{parent}:\n"));
        }
        if !out.ends_with('\n') {
            out.push('\n');
        }
        out.push_str(&format!("  {child}: {value}\n"));
    }
    out
}

fn extract_top_level(yaml: &str, key: &str) -> Option<String> {
    let prefix = format!("{key}: ");
    for line in yaml.lines() {
        if let Some(rest) = line.strip_prefix(&prefix) {
            return Some(clean_value(rest));
        }
    }
    None
}

fn extract_nested(yaml: &str, parent: &str, child: &str) -> Option<String> {
    let parent_marker = format!("{parent}:");
    let child_prefix = format!("{child}: ");
    let mut in_parent = false;
    for line in yaml.lines() {
        if line == parent_marker || line.starts_with(&format!("{parent_marker} ")) {
            in_parent = true;
            continue;
        }
        if in_parent {
            if line.starts_with(' ') {
                let trimmed = line.trim_start();
                if let Some(rest) = trimmed.strip_prefix(&child_prefix) {
                    return Some(clean_value(rest));
                }
            } else if !line.is_empty() {
                in_parent = false;
            }
        }
    }
    None
}

fn clean_value(s: &str) -> String {
    decode_yaml_escapes(
        s.trim().trim_matches('\'').trim_matches('"'),
    )
}

fn decode_yaml_escapes(s: &str) -> String {
    if !s.contains("\\u") && !s.contains("\\\"") && !s.contains("\\\\") {
        return s.to_string();
    }
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        match chars.next() {
            Some('u') => {
                let hex: String = (0..4).filter_map(|_| chars.next()).collect();
                if hex.len() == 4 {
                    if let Ok(code) = u32::from_str_radix(&hex, 16) {
                        if let Some(decoded) = char::from_u32(code) {
                            out.push(decoded);
                            continue;
                        }
                    }
                }
                out.push('\\');
                out.push('u');
                out.push_str(&hex);
            }
            Some('n') => out.push('\n'),
            Some('t') => out.push('\t'),
            Some('"') => out.push('"'),
            Some('\\') => out.push('\\'),
            Some(other) => {
                out.push('\\');
                out.push(other);
            }
            None => out.push('\\'),
        }
    }
    out
}
