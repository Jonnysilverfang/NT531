#!/usr/bin/env bash
# Mode B orchestrator. Plan generation is offline; execution is explicit and fail-closed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/experiment.yaml"
PROFILE=""
PLAN_ONLY=false
EXECUTE=false
EXPERIMENT_ID="experiment_$(date -u +%Y%m%dT%H%M%SZ)"
EXECUTION_MODE="${EXECUTION_MODE:-aws-remote}"
DUT_INSTANCE_ID="${DUT_INSTANCE_ID:-}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"

# Targets are infrastructure inventory, not experimental constants. Supply them
# from `terraform output` or explicit environment variables; there are no fake defaults.
TARGET_PEERING_IP="${TARGET_PEERING_IP:-}"
TARGET_TGW_IP="${TARGET_TGW_IP:-}"
DIRECT_TARGET_IP="${DIRECT_TARGET_IP:-}"
PRIVATELINK_ENDPOINT_IP="${PRIVATELINK_ENDPOINT_IP:-}"
TARGET_PEERING_INSTANCE_ID="${TARGET_PEERING_INSTANCE_ID:-}"
TARGET_TGW_INSTANCE_ID="${TARGET_TGW_INSTANCE_ID:-}"
DIRECT_TARGET_INSTANCE_ID="${DIRECT_TARGET_INSTANCE_ID:-}"

usage() {
    cat <<'EOF'
Usage:
  scripts/benchmark_runner.sh --plan-only [--profile validation|pilot|final]
  scripts/benchmark_runner.sh --execute --execution-mode aws-remote [options]

Options:
  --config PATH
  --profile validation|pilot|final
  --experiment-id ID
  --execution-mode aws-remote|local-emulation
  --plan-only                 Generate deterministic schedule; never call AWS or mutate networking.
  --execute                   Run preflight and the configured Mode B experiment.

AWS execution requires DUT_INSTANCE_ID, target IPs, and target instance IDs from
the deployed inventory. TC-01 records both host assignments; TC-03 requires the
direct and PrivateLink paths to resolve to DIRECT_TARGET_INSTANCE_ID.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --config) CONFIG_FILE="$2"; shift 2 ;;
        --profile) PROFILE="$2"; shift 2 ;;
        --experiment-id) EXPERIMENT_ID="$2"; shift 2 ;;
        --execution-mode) EXECUTION_MODE="$2"; shift 2 ;;
        --execution-mode=*) EXECUTION_MODE="${1#*=}"; shift ;;
        --local-emulation) EXECUTION_MODE=local-emulation; shift ;;
        --plan-only) PLAN_ONLY=true; shift ;;
        --execute) EXECUTE=true; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unsupported argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[ "${PLAN_ONLY}" = true ] || [ "${EXECUTE}" = true ] || {
    echo "Refusing implicit execution. Choose --plan-only or --execute." >&2
    exit 2
}
[ "${PLAN_ONLY}" = false ] || [ "${EXECUTE}" = false ] || {
    echo "--plan-only and --execute are mutually exclusive." >&2
    exit 2
}

profile_args=()
if [ -n "${PROFILE}" ]; then profile_args=(--profile "${PROFILE}"); fi

if [ "${PLAN_ONLY}" = true ]; then
    PLAN_OUTPUT="${PROJECT_ROOT}/results/mode_b/plans/${EXPERIMENT_ID}.json"
    "${PYTHON_BIN}" "${SCRIPT_DIR}/generate_run_plan.py" \
        --config "${CONFIG_FILE}" "${profile_args[@]}" \
        --experiment-id "${EXPERIMENT_ID}" --output "${PLAN_OUTPUT}"
    echo "PLAN_ONLY=PASS aws_verified=false empirical=false output=${PLAN_OUTPUT}"
    exit 0
fi

# The config is repository-controlled and validated before its shell-safe output is evaluated.
config_shell=$("${PYTHON_BIN}" "${SCRIPT_DIR}/load_experiment_config.py" \
    --config "${CONFIG_FILE}" "${profile_args[@]}" --format shell)
eval "${config_shell}"

case "${EXECUTION_MODE}" in
    aws-remote) ;;
    local-emulation)
        echo "LOCAL EMULATION mutates the selected local interface and is never empirical AWS evidence." >&2
        ;;
    *) echo "Invalid execution mode: ${EXECUTION_MODE}" >&2; exit 2 ;;
esac

source "${SCRIPT_DIR}/lib/common.sh"
source "${SCRIPT_DIR}/lib/ssm.sh"
source "${SCRIPT_DIR}/lib/metrics.sh"
source "${SCRIPT_DIR}/lib/metadata.sh"
source "${SCRIPT_DIR}/benchmarks/tc01_routing.sh"
source "${SCRIPT_DIR}/benchmarks/tc02_mtu.sh"
source "${SCRIPT_DIR}/benchmarks/tc03_privatelink.sh"
source "${SCRIPT_DIR}/benchmarks/tc04_packet_processing.sh"

for required in "${PYTHON_BIN}" ip iperf3 sockperf ethtool; do require_command "${required}"; done
if [ "${EXECUTION_MODE}" = aws-remote ]; then
    require_command aws
    require_command jq
    [ -n "${DUT_INSTANCE_ID}" ] || die "DUT_INSTANCE_ID is required"
    for name in TARGET_PEERING_INSTANCE_ID TARGET_TGW_INSTANCE_ID DIRECT_TARGET_INSTANCE_ID; do
        [ -n "${!name}" ] || die "${name} must come from the deployed Terraform inventory"
    done
    [ "${DUT_INSTANCE_ID}" = "${TARGET_PEERING_INSTANCE_ID}" ] || \
        die "DUT_INSTANCE_ID must match TARGET_PEERING_INSTANCE_ID for TC-02/TC-04 evidence"
else
    TARGET_PEERING_INSTANCE_ID="${TARGET_PEERING_INSTANCE_ID:-local-peering-target}"
    TARGET_TGW_INSTANCE_ID="${TARGET_TGW_INSTANCE_ID:-local-tgw-target}"
    DIRECT_TARGET_INSTANCE_ID="${DIRECT_TARGET_INSTANCE_ID:-local-shared-target}"
fi
for name in TARGET_PEERING_IP TARGET_TGW_IP DIRECT_TARGET_IP PRIVATELINK_ENDPOINT_IP; do
    [ -n "${!name}" ] || die "${name} must come from the deployed Terraform inventory"
done

"${SCRIPT_DIR}/preflight_check.sh" --scope "$([ "${EXECUTION_MODE}" = aws-remote ] && printf aws || printf offline)" \
    --config "${CONFIG_FILE}" "${profile_args[@]}" --dut-instance-id "${DUT_INSTANCE_ID}" --interface "${INTERFACE}"

ORIGINAL_MTU=$(ip link show dev "${INTERFACE}" | awk '/mtu/ {print $5; exit}')
EXPERIMENT_DIR="${PROJECT_ROOT}/${RESULTS_ROOT_REL}/${EXPERIMENT_ID}"
mkdir -p "${EXPERIMENT_DIR}"

cleanup() {
    local code=$?
    trap - EXIT INT TERM
    set +e
    if [ -n "${ORIGINAL_MTU:-}" ]; then sudo ip link set dev "${INTERFACE}" mtu "${ORIGINAL_MTU}"; fi
    if [ -n "${RUN_DIR:-}" ]; then
        run_on_dut remove_iptables_drop ""
        run_on_dut remove_xdp_native ""
        run_on_dut restore_original_mtu ""
    fi
    return "${code}"
}
trap cleanup EXIT INT TERM

for RUN_ID in $(seq 1 "${NUM_RUNS}"); do
    RUN_DIR="${EXPERIMENT_DIR}/run_$(printf '%03d' "${RUN_ID}")"
    RUN_SEED=$((RANDOM_SEED + RUN_ID * 1000))
    "${PYTHON_BIN}" "${SCRIPT_DIR}/manage_run_artifacts.py" init \
        --run-dir "${RUN_DIR}" --config "${CONFIG_FILE}" \
        --experiment-id "${EXPERIMENT_ID}" --run-id "${RUN_ID}" \
        --region "${AWS_REGION}" --profile "${EXPERIMENT_PROFILE}" --seed "${RUN_SEED}" \
        --data-mode "$([ "${EXECUTION_MODE}" = aws-remote ] && printf empirical_aws || printf local_emulation)"
    "${PYTHON_BIN}" "${SCRIPT_DIR}/manage_run_artifacts.py" record-target \
        --run-dir "${RUN_DIR}" --testcase tc01 --condition peering \
        --target-id "${TARGET_PEERING_INSTANCE_ID}" --target-address "${TARGET_PEERING_IP}" --path peering
    "${PYTHON_BIN}" "${SCRIPT_DIR}/manage_run_artifacts.py" record-target \
        --run-dir "${RUN_DIR}" --testcase tc01 --condition tgw \
        --target-id "${TARGET_TGW_INSTANCE_ID}" --target-address "${TARGET_TGW_IP}" --path tgw
    "${PYTHON_BIN}" "${SCRIPT_DIR}/manage_run_artifacts.py" record-target \
        --run-dir "${RUN_DIR}" --testcase tc03 --condition direct \
        --target-id "${DIRECT_TARGET_INSTANCE_ID}" --target-address "${DIRECT_TARGET_IP}" --path direct
    "${PYTHON_BIN}" "${SCRIPT_DIR}/manage_run_artifacts.py" record-target \
        --run-dir "${RUN_DIR}" --testcase tc03 --condition privatelink \
        --target-id "${DIRECT_TARGET_INSTANCE_ID}" --target-address "${PRIVATELINK_ENDPOINT_IP}" --path privatelink
    collect_environment_manifest
    run_on_dut start_daemons ""

    if [ "${TC01_ENABLED}" = true ]; then run_tc01; else record_disabled_schedule tc01 "$((RUN_SEED + 101))"; fi
    if [ "${TC02_ENABLED}" = true ]; then run_tc02; else record_disabled_schedule tc02 "$((RUN_SEED + 202))"; fi
    if [ "${TC03_ENABLED}" = true ]; then run_tc03; else record_disabled_schedule tc03 "$((RUN_SEED + 303))"; fi
    if [ "${TC04_ENABLED}" = true ]; then run_tc04; else record_disabled_schedule tc04 "$((RUN_SEED + 404))"; fi

    "${PYTHON_BIN}" "${SCRIPT_DIR}/manage_run_artifacts.py" finalize --run-dir "${RUN_DIR}"
    "${PYTHON_BIN}" "${SCRIPT_DIR}/manage_run_artifacts.py" verify --run-dir "${RUN_DIR}"
done

trap - EXIT INT TERM
cleanup
echo "MODE_B_COLLECTION=PASS runs=${NUM_RUNS} directory=${EXPERIMENT_DIR}"
echo "Analysis is intentionally separate; empirical conclusions require the Mode B analyzer and completeness gate."
