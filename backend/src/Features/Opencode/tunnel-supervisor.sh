#!/bin/sh

log_file=${OPENCODE_TUNNEL_LOG:-/tmp/cloudflared.log}
initial_delay=${OPENCODE_TUNNEL_RETRY_INITIAL_DELAY:-5}
max_delay=${OPENCODE_TUNNEL_RETRY_MAX_DELAY:-60}
retry_delay=$initial_delay
tunnel_pid=

stop_tunnel() {
  if [ -n "$tunnel_pid" ]; then
    kill "$tunnel_pid" 2>/dev/null || true
    wait "$tunnel_pid" 2>/dev/null || true
  fi
  exit 0
}

trap stop_tunnel INT TERM

while :; do
  started_at=$(date +%s)
  cloudflared tunnel --url http://127.0.0.1:4096 >>"$log_file" 2>&1 &
  tunnel_pid=$!
  wait "$tunnel_pid"
  exit_status=$?
  tunnel_pid=
  finished_at=$(date +%s)

  if [ "$((finished_at - started_at))" -ge 60 ]; then
    retry_delay=$initial_delay
  fi

  printf '[tunnel-supervisor] cloudflared exited with status %s; retrying in %s seconds\n' \
    "$exit_status" "$retry_delay" >>"$log_file"
  sleep "$retry_delay"

  if [ "$retry_delay" -lt "$max_delay" ]; then
    retry_delay=$((retry_delay * 2))
    if [ "$retry_delay" -gt "$max_delay" ]; then
      retry_delay=$max_delay
    fi
  fi
done
