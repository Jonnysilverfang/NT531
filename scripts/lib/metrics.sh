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
    local cpu_delta="$2"
    local load_output="$3"
    local loss_threshold="${SATURATION_LOSS_PCT:-1.0}"
    local p99_threshold="${SATURATION_P99_MS:-5.0}"
    local cpu_threshold="${SATURATION_CPU_PCT:-90.0}"

    "${PYTHON_BIN}" "${SCRIPT_DIR}/evaluate_saturation.py" \
        --probe-output "${probe_output}" \
        --cpu-delta "${cpu_delta}" \
        --load-output "${load_output}" \
        --loss-threshold "${loss_threshold}" \
        --p99-threshold-ms "${p99_threshold}" \
        --cpu-threshold "${cpu_threshold}"
}

icmp_probe() {
    local target="$1"
    local output="$2"
    local duration="${3:-${MEASUREMENT_SECONDS}}"
    ping -n -q -i 0.1 -w "${duration}" "${target}" > "${output}"
}
