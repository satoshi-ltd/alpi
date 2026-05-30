FROM python:3.11-slim

ENV ALPI_PLATFORM=docker \
    HOME=/data \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Only what the build needs — never the whole repo (a stray .venv / node_modules
# would otherwise leak ~1GB into the image).
COPY pyproject.toml README.md LICENSE ./
COPY alpi ./alpi
RUN pip install .

# --create-home on /data leaves it owned by uid 1000; no chown -R (that would
# duplicate /app into a second layer). The package lives in site-packages
# (root-owned, world-readable); /app source isn't needed at runtime.
RUN groupadd --gid 1000 alpi \
    && useradd --uid 1000 --gid 1000 --home-dir /data --create-home --shell /bin/sh alpi

COPY docker/entrypoint.sh /usr/local/bin/alpi-docker
RUN chmod +x /usr/local/bin/alpi-docker

VOLUME ["/data"]
# 49200 host control plane (desktop/mobile pairing) · 7423 ALP peer network.
# Override per-container with ALPI_HOST_TCP_PORT / ALPI_ALP_TCP_PORT.
EXPOSE 49200 7423
USER 1000:1000

ENTRYPOINT ["alpi-docker"]
