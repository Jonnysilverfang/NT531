#!/usr/bin/env bash

run_tc03() {
    local schedule=() load stage condition output_dir flood_pid
    local base_seed=$((RANDOM_SEED + RUN_ID * 1000 + 303))
    local saturation_file="${RUN_DIR}/tc03/saturation_events.jsonl"
    mkdir -p "${RUN_DIR}/tc03"

    stage=0
    for load in "${TC03_LOAD_PPS[@]}"; do
        stage=$((stage + 1))
        local stage_order=()
        mapfile -t stage_order < <(randomized_order "$((base_seed + stage))" "${TC03_CONDITIONS[@]}")
        for condition in "${stage_order[@]}"; do schedule+=("${load}:${condition}"); done
    done
    record_schedule tc03 "${base_seed}" "${schedule[@]}"

    local iptables_saturated=false
    local xdp_saturated=false
    for item in "${schedule[@]}"; do
        load="${item%%:*}"
        condition="${item##*:}"
        if [ "${condition}" = "iptables" ] && [ "${iptables_saturated}" = true ]; then continue; fi
        if [ "${condition}" = "xdp" ] && [ "${xdp_saturated}" = true ]; then continue; fi

        output_dir="${RUN_DIR}/tc03/load_${load}/${condition}"
        mkdir -p "${output_dir}"
        case "${condition}" in
            iptables) run_on_dut apply_iptables_drop "" ;;
            xdp) run_on_dut apply_xdp_native "" ;;
            *) die "Unexpected TC03 condition: ${condition}" ;;
        esac

        udp_load "${TARGET_PEERING_IP}" "${load}" "${WARMUP_SECONDS}" "${output_dir}/warmup_iperf3.json"
        run_on_dut snapshot_counters "${output_dir}/before.json"
        udp_load "${TARGET_PEERING_IP}" "${load}" "${MEASUREMENT_SECONDS}" "${output_dir}/load_iperf3.json" &
        flood_pid=$!
        latency_probe "${TARGET_PEERING_IP}" "${output_dir}/legitimate_probe.txt" "${MEASUREMENT_SECONDS}" 5202
        wait "${flood_pid}"
        run_on_dut snapshot_counters "${output_dir}/after.json"

        "${PYTHON_BIN}" "${SCRIPT_DIR}/calculate_softirq_delta.py" \
            --before "${output_dir}/before.json" --after "${output_dir}/after.json" \
            --condition "${condition}_load_${load}" --run-id "${RUN_ID}" \
            --output-json "${output_dir}/softirq_delta.json"

        local sat_result is_saturated
        sat_result=$(check_saturation \
            "${output_dir}/legitimate_probe.txt" \
            "${output_dir}/softirq_delta.json" \
            "${output_dir}/load_iperf3.json")
        printf '{"run_id":%s,"load_target_pps":%s,"condition":"%s","saturation":%s}\n' \
            "${RUN_ID}" "${load}" "${condition}" "${sat_result}" >> "${saturation_file}"

        is_saturated=$(printf '%s' "${sat_result}" | "${PYTHON_BIN}" -c \
            'import json,sys; print(str(json.load(sys.stdin)["saturated"]).lower())')
        if [ "${is_saturated}" = true ]; then
            if [ "${condition}" = iptables ]; then iptables_saturated=true; else xdp_saturated=true; fi
        fi

        if [ "${condition}" = iptables ]; then
            run_on_dut remove_iptables_drop ""
        else
            run_on_dut remove_xdp_native ""
        fi
        cooldown_pause
    done
}
