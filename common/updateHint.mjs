const LEGACY = "Docker: set the image tag to the new version in docker-compose.yml, then docker compose up -d. Source install: git pull and restart the daemon.";

export function canSelfUpdate(selfUpdate) {
  return selfUpdate !== false;
}

export function updateHint(installer, version) {
  if (installer === "docker") {
    return `Set the image tag to ${version || "the new version"} in docker-compose.yml, then docker compose up -d.`;
  }
  if (installer === "source") return "Run git pull and restart the daemon.";
  return LEGACY;
}
