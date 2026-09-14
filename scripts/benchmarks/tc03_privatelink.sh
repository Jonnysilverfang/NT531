#!/usr/bin/env bash

run_tc03() {
    local seed=$((RANDOM_SEED + RUN_ID * 1000 + 303))
    local order=()
    mapfile -t order < <(randomized_order "${seed}" "${TC03_CONDITIONS[@]}")
    record_schedule tc03 "${seed}" "${order[@]}"
    for condition in "${order[@]}"; do
        local target output_dir
        case "${condition}" in
            direct) target="${DIRECT_TARGET_IP}" ;;
            privatelink) target="${PRIVATELINK_ENDPOINT_IP}" ;;
            *) die "Unexpected TC03 condition: ${condition}" ;;
        esac
        output_dir="${RUN_DIR}/tc03/${condition}"
        mkdir -p "${output_dir}"
        latency_warmup "${target}"
        latency_probe "${target}" "${output_dir}/latency.txt"
        tcp_throughput "${target}" 1 "${output_dir}/iperf3.json"
        cooldown_pause
    done
}
