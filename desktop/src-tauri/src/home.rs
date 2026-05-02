use std::env;
use std::path::PathBuf;

pub fn resolve_root() -> Option<PathBuf> {
    Some(dirs::home_dir()?.join(".alpi"))
}

pub fn resolve_home(profile: Option<&str>) -> Option<PathBuf> {
    if let Ok(override_path) = env::var("ALPI_HOME") {
        return Some(expand_tilde(&override_path));
    }
    let root = resolve_root()?;
    let name = profile
        .map(|s| s.to_string())
        .unwrap_or_else(|| env::var("ALPI_PROFILE").unwrap_or_default());
    if name.is_empty() || name == "default" {
        Some(root)
    } else {
        Some(root.join("profiles").join(name))
    }
}

fn expand_tilde(s: &str) -> PathBuf {
    if let Some(rest) = s.strip_prefix("~/") {
        if let Some(home) = dirs::home_dir() {
            return home.join(rest);
        }
    }
    PathBuf::from(s)
}
