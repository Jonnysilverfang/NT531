#!/usr/bin/env bash

run_tc04() {
    local schedule=() load stage seed condition output_dir flood_pid
    local base_seed=$((RANDOM_SEED + RUN_ID * 1000 + 404))
    local saturation_file="${RUN_DIR}/tc04/saturation_events.jsonl"
    mkdir -p "${RUN_DIR}/tc04"
    
    stage=0
    for load in "${TC04_LOAD_PPS[@]}"; do
        stage=$((stage + 1))
        local stage_order=()
        mapfile -t stage_order < <(randomized_order "$((base_seed + stage))" "${TC04_CONDITIONS[@]}")
        for condition in "${stage_order[@]}"; do schedule+=("${load}:${condition}"); done
    done
    record_schedule tc04 "${base_seed}" "${schedule[@]}"

    local iptables_saturated=false
    local xdp_saturated=false

    for item in "${schedule[@]}"; do
        load="${item%%:*}"
        condition="${item##*:}"
        
        if [ "${condition}" = "iptables" ] && [ "${iptables_saturated}" = true ]; then
            echo "Skipping iptables load ${load}: already saturated" >&2
            continue
        fi
        if [ "${condition}" = "xdp" ] && [ "${xdp_saturated}" = true ]; then
            echo "Skipping xdp load ${load}: already saturated" >&2
            continue
        fi
        
        output_dir="${RUN_DIR}/tc04/load_${load}/${condition}"
        mkdir -p "${output_dir}"
        
        case "${condition}" in
            iptables) run_on_dut apply_iptables_drop "" ;;
            xdp) run_on_dut apply_xdp_native "" ;;
            *) die "Unexpected TC04 condition: ${condition}" ;;
        esac

        udp_load "${TARGET_PEERING_IP}" "${load}" "${WARMUP_SECONDS}" "${output_dir}/warmup_iperf3.json"
        run_on_dut snapshot_counters "${output_dir}/before.json"
        udp_load "${TARGET_PEERING_IP}" "${load}" "${MEASUREMENT_SECONDS}" "${output_dir}/load_iperf3.json" &
        flood_pid=$!
        latency_probe "${TARGET_PEERING_IP}" "${output_dir}/legitimate_probe.txt" "${MEASUREMENT_SECONDS}" 5202
        wait "${flood_pid}"
        run_on_dut snapshot_counters "${output_dir}/after.json"
        
        python3 "${SCRIPT_DIR}/calculate_softirq_delta.py" \
            --before "${output_dir}/before.json" --after "${output_dir}/after.json" \
            --condition "${condition}_load_${load}" --run-id "${RUN_ID}" \
            --output-json "${output_dir}/softirq_delta.json"
        
        local sat_result
        sat_result=$(check_saturation "${output_dir}/legitimate_probe.txt" "${output_dir}/after.json")
        echo "{\"run_id\":${RUN_ID},\"load_target\":${load},\"condition\":\"${condition}\",\"saturation\":${sat_result}}" >> "${saturation_file}"
        
        local is_saturated
        is_saturated=$(echo "${sat_result}" | grep -o '"saturated":[^,}]*' | cut -d: -f2)
        if [ "${is_saturated}" = "true" ]; then
            if [ "${condition}" = "iptables" ]; then
                iptables_saturated=true
                echo "iptables saturated at load ${load}" >&2
            else
                xdp_saturated=true
                echo "xdp saturated at load ${load}" >&2
            fi
        fi
        
        if [ "${condition}" = iptables ]; then
            run_on_dut remove_iptables_drop ""
        else
            run_on_dut remove_xdp_native ""
        fi
        cooldown_pause
    done
}
