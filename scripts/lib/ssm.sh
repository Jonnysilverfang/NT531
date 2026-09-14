#!/usr/bin/env bash

run_on_dut() {
    local action="$1"
    local target_local_file="${2:-}"
    case "${action}" in
        start_daemons|snapshot_counters|apply_iptables_drop|remove_iptables_drop|apply_xdp_native|remove_xdp_native|restore_original_mtu|set_mtu_1500|set_mtu_9001) ;;
        *) die "DUT action is not allowlisted: ${action}" ;;
    esac

    if [ "${EXECUTION_MODE}" = "local-emulation" ]; then
        bash "${SCRIPT_DIR}/dut_server_setup.sh" "${action}" "${INTERFACE}" "${target_local_file}"
        return
    fi

    local cmd_id invocation_json status response_code stdout_content stderr_content
    cmd_id=$(aws ssm send-command \
        --region "${AWS_REGION}" \
        --instance-ids "${DUT_INSTANCE_ID}" \
        --document-name AWS-RunShellScript \
        --parameters "commands=[\"sudo bash /opt/capstone/scripts/dut_server_setup.sh ${action} ${INTERFACE} /tmp/dut_snapshot.json\"]" \
        --query Command.CommandId --output text)
    mkdir -p "${RUN_DIR}/commands"

    status="Pending"
    for _attempt in $(seq 1 120); do
        if invocation_json=$(aws ssm get-command-invocation \
            --region "${AWS_REGION}" --command-id "${cmd_id}" \
            --instance-id "${DUT_INSTANCE_ID}" 2>/dev/null); then
            printf '%s\n' "${invocation_json}" > "${RUN_DIR}/commands/${cmd_id}_invocation.json"
            status=$(printf '%s' "${invocation_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("Status", "Unknown"))')
            case "${status}" in
                Success|Cancelled|TimedOut|Failed|Cancelling) break ;;
            esac
        fi
        sleep 1
    done
    [ -n "${invocation_json:-}" ] || die "No SSM invocation result for ${cmd_id}"
    stdout_content=$(printf '%s' "${invocation_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("StandardOutputContent", ""))')
    stderr_content=$(printf '%s' "${invocation_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("StandardErrorContent", ""))')
    response_code=$(printf '%s' "${invocation_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("ResponseCode", -1))')
    printf '%s\n' "${stdout_content}" > "${RUN_DIR}/commands/${cmd_id}_stdout.log"
    printf '%s\n' "${stderr_content}" > "${RUN_DIR}/commands/${cmd_id}_stderr.log"
    [ "${status}" = "Success" ] && [ "${response_code}" -eq 0 ] || \
        die "SSM action ${action} failed: status=${status}, ResponseCode=${response_code}"

    if [ "${action}" = "snapshot_counters" ] && [ -n "${target_local_file}" ]; then
        printf '%s' "${stdout_content}" | python3 -c '
import re, sys
match = re.search(r"___DUT_SNAPSHOT_JSON_BEGIN___(.*?)___DUT_SNAPSHOT_JSON_END___", sys.stdin.read(), re.S)
if not match:
    raise SystemExit("missing DUT snapshot sentinel")
print(match.group(1).strip())
' > "${target_local_file}"
    fi
}
