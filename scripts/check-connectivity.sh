#!/usr/bin/env bash
# Connectivity evidence only: not a throughput benchmark.
set -euo pipefail
mode=${1:-unknown}
case "$mode" in peering|tgw) ;; *) echo 'Usage: bash check-connectivity.sh peering|tgw' >&2; exit 1 ;; esac
own_ip=$(ip -4 -o addr show dev ens5 scope global | awk '{split($4,a,"/"); print a[1]; exit}')
mkdir -p "$HOME/nt531-results"
log=$(mktemp "$HOME/nt531-results/connectivity-$mode-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.txt")
exec > >(tee "$log") 2>&1
printf 'UTC=%s source=%s declared_mode=%s\n' "$(date -u +%FT%TZ)" "$own_ip" "$mode"
failed=0
for target in 10.10.10.212 10.20.10.155 10.30.10.212 10.40.10.155; do
  [[ "$target" == "$own_ip" ]] && continue
  if ping -c 2 -W 2 "$target"; then
    printf 'PING PASS %s -> %s\n' "$own_ip" "$target"
  else
    printf 'PING FAIL %s -> %s\n' "$own_ip" "$target"
    failed=1
  fi
  for port in 5201 5202 5203; do
    if timeout 3 bash -c 'exec 3<>/dev/tcp/$1/$2' _ "$target" "$port"; then
      printf 'TCP PASS %s -> %s:%s\n' "$own_ip" "$target" "$port"
    else
      printf 'TCP FAIL %s -> %s:%s\n' "$own_ip" "$target" "$port"
      failed=1
    fi
  done
  # Bounded application smoke test: 1 Mbit/s for 2 seconds, not a capacity test.
  smoke=$(mktemp "$HOME/nt531-results/smoke-$mode-$target-XXXXXX.json")
  if timeout 12 iperf3 -c "$target" -p 5201 -b 1M -t 2 -J > "$smoke" &&
     jq -e '(.error == null) and (.end.sum_received.bytes > 0)' "$smoke" >/dev/null; then
    printf 'IPERF PASS %s -> %s (1 Mbit/s, 2 seconds)\n' "$own_ip" "$target"
  else
    printf 'IPERF FAIL %s -> %s; see %s\n' "$own_ip" "$target" "$smoke"
    failed=1
  fi
done
printf 'Evidence: %s\n' "$log"
exit "$failed"
