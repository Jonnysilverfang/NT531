#!/usr/bin/env bash

collect_environment_manifest() {
    python3 "${SCRIPT_DIR}/collect_environment_manifest.py" \
        --output "${RUN_DIR}/environment.json" \
        --interface "${INTERFACE}" \
        --region "${AWS_REGION}" \
        --availability-zone "${AVAILABILITY_ZONE:-unknown}" \
        --instance-id "${CLIENT_INSTANCE_ID:-unknown}" \
        --instance-type "${INSTANCE_TYPE:-unknown}" \
        --ami-id "${AMI_ID:-unknown}"
}
