FROM python:3.11-slim

ARG TARGETARCH
ARG TTYD_VERSION=1.7.7

ENV ALPI_PLATFORM=umbrel \
    ALPI_TTYD_PORT=8080 \
    DEBIAN_FRONTEND=noninteractive \
    HOME=/data \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
        amd64) ttyd_arch="x86_64"; ttyd_sha="8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55" ;; \
        arm64) ttyd_arch="aarch64"; ttyd_sha="b38acadd89d1d396a0f5649aa52c539edbad07f4bc7348b27b4f4b7219dd4165" ;; \
        *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${ttyd_arch}" -o /usr/local/bin/ttyd; \
    echo "${ttyd_sha}  /usr/local/bin/ttyd" | sha256sum -c -; \
    chmod +x /usr/local/bin/ttyd

WORKDIR /app
COPY . /app

RUN pip install .

RUN groupadd --gid 1000 alpi \
    && useradd --uid 1000 --gid 1000 --home-dir /data --create-home --shell /bin/sh alpi \
    && chown -R 1000:1000 /app /data

COPY deploy/umbrel/alpi/entrypoint.sh /usr/local/bin/alpi-umbrel
RUN chmod +x /usr/local/bin/alpi-umbrel

VOLUME ["/data"]
EXPOSE 8080
USER 1000:1000

ENTRYPOINT ["alpi-umbrel"]
