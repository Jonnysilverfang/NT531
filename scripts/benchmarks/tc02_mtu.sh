#!/usr/bin/env bash

run_tc02() {
    local seed=$((RANDOM_SEED + RUN_ID * 1000 + 202))
    local cells=() order=()
    local mtu streams
    for mtu in "${TC02_MTUS[@]}"; do
        for streams in "${TC02_STREAMS[@]}"; do cells+=("mtu${mtu}-p${streams}"); done
    done
    mapfile -t order < <(randomized_order "${seed}" "${cells[@]}")
    record_schedule tc02 "${seed}" "${order[@]}"
    for cell in "${order[@]}"; do
        mtu="${cell#mtu}"; mtu="${mtu%%-*}"
        streams="${cell##*-p}"
        local output_dir="${RUN_DIR}/tc02/${cell}"
        mkdir -p "${output_dir}"
        sudo ip link set dev "${INTERFACE}" mtu "${mtu}"
        run_on_dut "set_mtu_${mtu}" ""
        iperf3 -c "${TARGET_PEERING_IP}" -P "${streams}" -t "${WARMUP_SECONDS}" >/dev/null
        run_on_dut snapshot_counters "${output_dir}/before.json"
        bash "${SCRIPT_DIR}/collect_ena_metrics.sh" "${output_dir}/ena_before.txt" "${INTERFACE}"
        tcp_throughput "${TARGET_PEERING_IP}" "${streams}" "${output_dir}/iperf3.json"
        run_on_dut snapshot_counters "${output_dir}/after.json"
        bash "${SCRIPT_DIR}/collect_ena_metrics.sh" "${output_dir}/ena_after.txt" "${INTERFACE}"
        "${PYTHON_BIN}" "${SCRIPT_DIR}/calculate_softirq_delta.py" \
            --before "${output_dir}/before.json" --after "${output_dir}/after.json" \
            --condition "${cell}" --run-id "${RUN_ID}" --output-json "${output_dir}/softirq_delta.json"
        cooldown_pause
    done
    sudo ip link set dev "${INTERFACE}" mtu "${ORIGINAL_MTU}"
    run_on_dut restore_original_mtu ""
}
