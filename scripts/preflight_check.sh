#!/usr/bin/env bash
# Offline by default. AWS checks require an explicit --scope aws flag.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/experiment.yaml"
PROFILE=""
SCOPE="offline"
DUT_INSTANCE_ID="${DUT_INSTANCE_ID:-}"
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
INTERFACE="${INTERFACE:-eth0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --scope) SCOPE="${2:?--scope requires offline or aws}"; shift 2 ;;
        --config) CONFIG_FILE="$2"; shift 2 ;;
        --profile) PROFILE="$2"; shift 2 ;;
        --dut-instance-id) DUT_INSTANCE_ID="$2"; shift 2 ;;
        --interface) INTERFACE="$2"; shift 2 ;;
        *) echo "PREFLIGHT_ERROR: unsupported argument: $1" >&2; exit 2 ;;
    esac
done

[ "${SCOPE}" = "offline" ] || [ "${SCOPE}" = "aws" ] || {
    echo "PREFLIGHT_ERROR: --scope must be offline or aws" >&2
    exit 2
}

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); printf '[PASS] %s\n' "$1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); printf '[FAIL] %s\n' "$1" >&2; }
check_command() {
    if command -v "$1" >/dev/null 2>&1; then pass "command:$1"; else fail "command:$1"; fi
}

check_command "${PYTHON_BIN}"
if [ -n "${PROFILE}" ]; then
    if "${PYTHON_BIN}" "${SCRIPT_DIR}/load_experiment_config.py" --config "${CONFIG_FILE}" --profile "${PROFILE}" >/dev/null; then
        pass "experiment-config"
    else
        fail "experiment-config"
    fi
else
    if "${PYTHON_BIN}" "${SCRIPT_DIR}/load_experiment_config.py" --config "${CONFIG_FILE}" >/dev/null; then
        pass "experiment-config"
    else
        fail "experiment-config"
    fi
fi

for path in \
    "${SCRIPT_DIR}/benchmark_runner.sh" \
    "${SCRIPT_DIR}/manage_run_artifacts.py" \
    "${PROJECT_ROOT}/terraform/main.tf" \
    "${PROJECT_ROOT}/docs/MODE_B_EXPERIMENTAL_PROTOCOL.md"; do
    if [ -f "${path}" ]; then pass "file:${path#${PROJECT_ROOT}/}"; else fail "file:${path#${PROJECT_ROOT}/}"; fi
done

if command -v terraform >/dev/null 2>&1; then
    if terraform -chdir="${PROJECT_ROOT}/terraform" fmt -check -diff >/dev/null; then
        pass "terraform-fmt"
    else
        fail "terraform-fmt"
    fi
else
    fail "terraform-cli-unavailable"
fi

if [ "${SCOPE}" = "aws" ]; then
    for required in aws jq ip ethtool iperf3 sockperf bpftool clang; do check_command "${required}"; done
    if [ -n "${DUT_INSTANCE_ID}" ]; then pass "dut-instance-id"; else fail "dut-instance-id"; fi
    if aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1; then
        pass "aws-identity"
    else
        fail "aws-identity"
    fi
    if [ -n "${DUT_INSTANCE_ID}" ] && \
       [ "$(aws ssm describe-instance-information --region "${AWS_REGION}" \
           --filters "Key=InstanceIds,Values=${DUT_INSTANCE_ID}" \
           --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null)" = "Online" ]; then
        pass "ssm-online"
    else
        fail "ssm-online"
    fi
    if ip link show dev "${INTERFACE}" >/dev/null 2>&1; then pass "interface:${INTERFACE}"; else fail "interface:${INTERFACE}"; fi
fi

printf 'PREFLIGHT_RESULT scope=%s aws_verified=%s pass=%s fail=%s\n' \
    "${SCOPE}" "$([ "${SCOPE}" = "aws" ] && printf true || printf false)" "${PASS_COUNT}" "${FAIL_COUNT}"
[ "${FAIL_COUNT}" -eq 0 ]
