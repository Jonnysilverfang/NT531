#!/usr/bin/env bash

latency_probe() {
    local target="$1"
    local output="$2"
    local duration="${3:-${MEASUREMENT_SECONDS}}"
    local port="${4:-5202}"
    sockperf ping-pong -i "${target}" --port "${port}" --tcp -t "${duration}" --full-rtt \
        | tee "${output}"
}

latency_warmup() {
    local target="$1"
    local port="${2:-5202}"
    sockperf ping-pong -i "${target}" --port "${port}" --tcp -t "${WARMUP_SECONDS}" --full-rtt \
        >/dev/null
}

tcp_throughput() {
    local target="$1"
    local streams="$2"
    local output="$3"
    iperf3 -c "${target}" -P "${streams}" -t "${MEASUREMENT_SECONDS}" -J > "${output}"
}

udp_load() {
    local target="$1"
    local pps="$2"
    local duration="$3"
    local output="$4"
    local bits_per_second=$((pps * UDP_PAYLOAD_BYTES * 8))
    iperf3 -c "${target}" -u -b "${bits_per_second}" -l "${UDP_PAYLOAD_BYTES}" \
        -p 5201 -t "${duration}" -J > "${output}"
}

check_saturation() {
    local probe_output="$1"
    local cpu_snapshot="$2"
    local loss_threshold="${SATURATION_LOSS_PCT:-1.0}"
    local p99_threshold="${SATURATION_P99_MS:-5.0}"
    local cpu_threshold="${SATURATION_CPU_PCT:-90.0}"
    
    local loss_pct=0
    local p99_ms=0
    local cpu_pct=0
    local saturated=false
    local reason=""
    
    if [ -f "${probe_output}" ]; then
        loss_pct=$(awk '/^#\[Packets lost\]/ {print $4}' "${probe_output}" | sed 's/%//' || echo "0")
        p99_ms=$(awk '/percentile 99\.000/ {print $3}' "${probe_output}" || echo "0")
    fi
    
    if [ -f "${cpu_snapshot}" ] && command -v python3 >/dev/null; then
        cpu_pct=$(python3 -c "
import json, sys
try:
    with open('${cpu_snapshot}') as f:
        d = json.load(f)
    total = sum(d.get('cpu', {}).values())
    idle = d.get('cpu', {}).get('idle', 0)
    print(round((total - idle) / total * 100, 2) if total > 0 else 0)
except: print(0)
" 2>/dev/null || echo "0")
    fi
    
    if (( $(echo "${loss_pct} > ${loss_threshold}" | bc -l 2>/dev/null || echo 0) )); then
        saturated=true
        reason="loss=${loss_pct}% > ${loss_threshold}%"
    elif (( $(echo "${p99_ms} > ${p99_threshold}" | bc -l 2>/dev/null || echo 0) )); then
        saturated=true
        reason="p99=${p99_ms}ms > ${p99_threshold}ms"
    elif (( $(echo "${cpu_pct} > ${cpu_threshold}" | bc -l 2>/dev/null || echo 0) )); then
        saturated=true
        reason="cpu=${cpu_pct}% > ${cpu_threshold}%"
    fi
    
    echo "{\"saturated\":${saturated},\"loss_pct\":${loss_pct},\"p99_ms\":${p99_ms},\"cpu_pct\":${cpu_pct},\"reason\":\"${reason}\"}"
}
