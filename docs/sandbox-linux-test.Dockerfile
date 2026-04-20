FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    bubblewrap curl python3 python3-venv ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH=/root/.local/bin:$PATH

WORKDIR /alf
