export const UPDATE_HINT_CASES = [
  ["docker", "0.16.19", "Set the image tag to 0.16.19 in docker-compose.yml, then docker compose up -d."],
  ["docker", null, "Set the image tag to the new version in docker-compose.yml, then docker compose up -d."],
  ["source", "0.16.19", "Run git pull and restart the daemon."],
  ["dev", "0.16.19", "Docker: set the image tag to the new version in docker-compose.yml, then docker compose up -d. Source install: git pull and restart the daemon."],
];
