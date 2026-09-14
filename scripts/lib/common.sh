#!/usr/bin/env bash

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

randomized_order() {
    local seed="$1"
    shift
    "${PYTHON_BIN}" - "$seed" "$@" <<'PY'
import random
import sys
items = sys.argv[2:]
random.Random(int(sys.argv[1])).shuffle(items)
print("\n".join(items))
PY
}

warmup_pause() {
    log "Warmup ${WARMUP_SECONDS}s"
    sleep "${WARMUP_SECONDS}"
}

cooldown_pause() {
    log "Cooldown ${COOLDOWN_SECONDS}s"
    sleep "${COOLDOWN_SECONDS}"
}

record_schedule() {
    local testcase="$1"
    local seed="$2"
    shift 2
    "${PYTHON_BIN}" "${SCRIPT_DIR}/manage_run_artifacts.py" record-schedule \
        --run-dir "${RUN_DIR}" --testcase "${testcase}" --seed "${seed}" "$@"
}

record_disabled_schedule() {
    record_schedule "$1" "$2" disabled
}

snapshot_delta() {
    local before="$1"
    local after="$2"
    local condition="$3"
    local output="$4"
    run_on_dut snapshot_counters "${before}"
    "$5"
    run_on_dut snapshot_counters "${after}"
    "${PYTHON_BIN}" "${SCRIPT_DIR}/calculate_softirq_delta.py" \
        --before "${before}" --after "${after}" --condition "${condition}" \
        --run-id "${RUN_ID}" --output-json "${output}"
}
