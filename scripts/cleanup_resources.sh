#!/usr/bin/env bash
# Review-first Terraform teardown. This script never performs ad-hoc AWS deletion.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"
EXPECTED_REGION="us-east-1"
EXPECTED_CONFIRMATION="DESTROY-nt531-netperf-us-east-1"

command -v terraform >/dev/null 2>&1 || { echo "Terraform CLI is required." >&2; exit 1; }
[ -f "${TERRAFORM_DIR}/terraform.tfstate" ] || {
    echo "No local Terraform state found; refusing ad-hoc resource discovery/deletion." >&2
    exit 1
}

cd "${TERRAFORM_DIR}"
actual_region=$(terraform output -json inventory | python3 -c 'import json,sys; print(json.load(sys.stdin)["region"])')
[ "${actual_region}" = "${EXPECTED_REGION}" ] || { echo "Unexpected state Region: ${actual_region}" >&2; exit 1; }

terraform plan -destroy -out=destroy.tfplan
echo "Destroy plan created. Review it before continuing."
[ "${CONFIRM_DESTROY:-}" = "${EXPECTED_CONFIRMATION}" ] || {
    echo "Set CONFIRM_DESTROY=${EXPECTED_CONFIRMATION} only after explicit approval." >&2
    exit 2
}
terraform apply destroy.tfplan
