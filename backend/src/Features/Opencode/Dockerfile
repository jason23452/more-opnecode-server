FROM node:22-bookworm-slim
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates python3 python3-venv procps && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    npm install --global pnpm opencode-ai @opencode-ai/sdk && \
    case "$TARGETARCH" in \
      amd64) cloudflared_arch=amd64 ;; \
      arm64) cloudflared_arch=arm64 ;; \
      *) echo "Unsupported TARGETARCH: ${TARGETARCH:-unset} (supported: amd64, arm64)" >&2; exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${cloudflared_arch}" -o /usr/local/bin/cloudflared && \
    chmod +x /usr/local/bin/cloudflared && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:${PATH}"
COPY tunnel-supervisor.sh /usr/local/bin/tunnel-supervisor.sh
COPY pty_runner.py /usr/local/bin/opencode-pty-runner
RUN chmod +x /usr/local/bin/tunnel-supervisor.sh
EXPOSE 4096
CMD ["sh", "-c", "opencode serve --hostname 0.0.0.0 --port 4096 & opencode_pid=$!; sleep 3; /usr/local/bin/tunnel-supervisor.sh & tunnel_supervisor_pid=$!; wait $opencode_pid; server_status=$?; kill -TERM $tunnel_supervisor_pid 2>/dev/null || true; wait $tunnel_supervisor_pid 2>/dev/null || true; exit $server_status"]
