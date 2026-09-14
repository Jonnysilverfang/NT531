#!/usr/bin/env bash

run_tc01() {
    local seed=$((RANDOM_SEED + RUN_ID * 1000 + 101))
    local order=()
    mapfile -t order < <(randomized_order "${seed}" "${TC01_CONDITIONS[@]}")
    record_schedule tc01 "${seed}" "${order[@]}"
    for condition in "${order[@]}"; do
        local target label output_dir
        case "${condition}" in
            peering) target="${TARGET_PEERING_IP}"; label="peering" ;;
            tgw) target="${TARGET_TGW_IP}"; label="tgw" ;;
            *) die "Unexpected TC01 condition: ${condition}" ;;
        esac
        output_dir="${RUN_DIR}/tc01/${label}"
        mkdir -p "${output_dir}"
        latency_warmup "${target}"
        latency_probe "${target}" "${output_dir}/latency.txt"
        cooldown_pause
    done
}
