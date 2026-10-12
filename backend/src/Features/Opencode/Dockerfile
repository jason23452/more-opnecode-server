FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates python3 python3-venv && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    npm install --global pnpm opencode-ai @opencode-ai/sdk && \
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && \
    chmod +x /usr/local/bin/cloudflared && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:${PATH}"
EXPOSE 4096
CMD ["sh", "-c", "opencode serve --hostname 0.0.0.0 --port 4096 & opencode_pid=$!; sleep 3; cloudflared tunnel --url http://127.0.0.1:4096 >/tmp/cloudflared.log 2>&1 & wait $opencode_pid"]
