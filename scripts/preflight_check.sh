#!/usr/bin/env bash
# Fail-closed preflight. AWS scope must run on the deployed EC2 client.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${PROJECT_ROOT}/experiment.yaml"
PROFILE=""
SCOPE="offline"
INTERFACE="${INTERFACE:-eth0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUTPUT_DIR=""

ACCOUNT_ID=""
CLIENT_INSTANCE_ID=""
PEERING_INSTANCE_ID=""
TGW_INSTANCE_ID=""
PEERING_IP=""
TGW_IP=""
EXPECTED_AMI_ID=""
EXPECTED_INSTANCE_TYPE="c6i.large"
CLIENT_ROUTE_TABLE_ID=""
PEERING_ROUTE_TABLE_ID=""
TGW_ROUTE_TABLE_ID=""
PEERING_CONNECTION_ID=""
TRANSIT_GATEWAY_ID=""
SERVER_SECURITY_GROUP_ID=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --scope) SCOPE="${2:?}"; shift 2 ;;
        --config) CONFIG_FILE="${2:?}"; shift 2 ;;
        --profile) PROFILE="${2:?}"; shift 2 ;;
        --interface) INTERFACE="${2:?}"; shift 2 ;;
        --output-dir) OUTPUT_DIR="${2:?}"; shift 2 ;;
        --account-id) ACCOUNT_ID="${2:?}"; shift 2 ;;
        --client-instance-id) CLIENT_INSTANCE_ID="${2:?}"; shift 2 ;;
        --peering-instance-id) PEERING_INSTANCE_ID="${2:?}"; shift 2 ;;
        --tgw-instance-id) TGW_INSTANCE_ID="${2:?}"; shift 2 ;;
        --peering-ip) PEERING_IP="${2:?}"; shift 2 ;;
        --tgw-ip) TGW_IP="${2:?}"; shift 2 ;;
        --expected-ami-id) EXPECTED_AMI_ID="${2:?}"; shift 2 ;;
        --expected-instance-type) EXPECTED_INSTANCE_TYPE="${2:?}"; shift 2 ;;
        --client-route-table-id) CLIENT_ROUTE_TABLE_ID="${2:?}"; shift 2 ;;
        --peering-route-table-id) PEERING_ROUTE_TABLE_ID="${2:?}"; shift 2 ;;
        --tgw-route-table-id) TGW_ROUTE_TABLE_ID="${2:?}"; shift 2 ;;
        --peering-connection-id) PEERING_CONNECTION_ID="${2:?}"; shift 2 ;;
        --transit-gateway-id) TRANSIT_GATEWAY_ID="${2:?}"; shift 2 ;;
        --server-security-group-id) SERVER_SECURITY_GROUP_ID="${2:?}"; shift 2 ;;
        *) printf 'PREFLIGHT_ERROR unsupported argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done

[ "${SCOPE}" = offline ] || [ "${SCOPE}" = aws ] || { echo "PREFLIGHT_ERROR invalid scope" >&2; exit 2; }

PASS_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); printf '[PASS] %s\n' "$1"; }
die() { printf '[FAIL] %s\n' "$1" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "missing command:$1"; pass "command:$1"; }

require_command "${PYTHON_BIN}"
profile_args=()
if [ -n "${PROFILE}" ]; then profile_args=(--profile "${PROFILE}"); fi
config_shell=$("${PYTHON_BIN}" "${SCRIPT_DIR}/load_experiment_config.py" --config "${CONFIG_FILE}" "${profile_args[@]}" --format shell)
eval "${config_shell}"
pass "experiment-config:${AWS_REGION}/${AVAILABILITY_ZONE}"

for path in "${SCRIPT_DIR}/benchmark_runner.sh" "${SCRIPT_DIR}/dut_server_setup.sh" \
    "${PROJECT_ROOT}/ebpf/ebpf_loader.sh" "${PROJECT_ROOT}/ebpf/xdp_packet_filter.c"; do
    [ -s "${path}" ] || die "missing runtime file:${path}"
done
pass "runtime-files"

if [ "${SCOPE}" = offline ]; then
    printf 'PREFLIGHT_RESULT scope=offline aws_verified=false pass=%s fail=0\n' "${PASS_COUNT}"
    exit 0
fi

for required in aws jq ip ping ethtool iperf3 sockperf bpftool clang curl timeout; do require_command "${required}"; done

for name in ACCOUNT_ID CLIENT_INSTANCE_ID PEERING_INSTANCE_ID TGW_INSTANCE_ID PEERING_IP TGW_IP \
    EXPECTED_AMI_ID EXPECTED_INSTANCE_TYPE CLIENT_ROUTE_TABLE_ID PEERING_ROUTE_TABLE_ID \
    TGW_ROUTE_TABLE_ID PEERING_CONNECTION_ID TRANSIT_GATEWAY_ID SERVER_SECURITY_GROUP_ID; do
    [ -n "${!name}" ] || die "missing required inventory:${name}"
done

if [ -z "${OUTPUT_DIR}" ]; then
    OUTPUT_DIR="${PROJECT_ROOT}/results/mode_b/preflight/$(date -u +%Y%m%dT%H%M%SZ)"
fi
[ ! -e "${OUTPUT_DIR}" ] || die "refusing to overwrite preflight directory:${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}/ssm"

identity_json=$(aws sts get-caller-identity --region "${AWS_REGION}")
printf '%s\n' "${identity_json}" > "${OUTPUT_DIR}/caller_identity.json"
[ "$(printf '%s' "${identity_json}" | jq -r .Account)" = "${ACCOUNT_ID}" ] || die "AWS account mismatch"
pass "aws-account:${ACCOUNT_ID}"

token=$(curl --fail --silent --show-error --request PUT \
    --header 'X-aws-ec2-metadata-token-ttl-seconds: 60' \
    http://169.254.169.254/latest/api/token)
imds_doc=$(curl --fail --silent --show-error \
    --header "X-aws-ec2-metadata-token: ${token}" \
    http://169.254.169.254/latest/dynamic/instance-identity/document)
printf '%s\n' "${imds_doc}" > "${OUTPUT_DIR}/client_imds_identity.json"
[ "$(printf '%s' "${imds_doc}" | jq -r .instanceId)" = "${CLIENT_INSTANCE_ID}" ] || die "preflight is not running on the Terraform client"
[ "$(printf '%s' "${imds_doc}" | jq -r .region)" = "${AWS_REGION}" ] || die "client Region mismatch"
[ "$(printf '%s' "${imds_doc}" | jq -r .availabilityZone)" = "${AVAILABILITY_ZONE}" ] || die "client AZ mismatch"
[ "$(printf '%s' "${imds_doc}" | jq -r .instanceType)" = "${EXPECTED_INSTANCE_TYPE}" ] || die "client type mismatch"
[ "$(printf '%s' "${imds_doc}" | jq -r .imageId)" = "${EXPECTED_AMI_ID}" ] || die "client AMI mismatch"
pass "ec2-client-identity"

instances_json=$(aws ec2 describe-instances --region "${AWS_REGION}" \
    --instance-ids "${CLIENT_INSTANCE_ID}" "${PEERING_INSTANCE_ID}" "${TGW_INSTANCE_ID}")
printf '%s\n' "${instances_json}" > "${OUTPUT_DIR}/instances.json"
"${PYTHON_BIN}" - "${OUTPUT_DIR}/instances.json" "${EXPECTED_AMI_ID}" "${EXPECTED_INSTANCE_TYPE}" "${AVAILABILITY_ZONE}" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
expected_ami, expected_type, expected_az = sys.argv[2:]
instances = [i for r in payload["Reservations"] for i in r["Instances"]]
if len(instances) != 3:
    raise SystemExit("expected exactly three instances")
for instance in instances:
    actual = (instance["State"]["Name"], instance["ImageId"], instance["InstanceType"], instance["Placement"]["AvailabilityZone"])
    expected = ("running", expected_ami, expected_type, expected_az)
    if actual != expected:
        raise SystemExit(f"instance drift {instance['InstanceId']}: {actual} != {expected}")
PY
pass "three-identical-running-instances"

ssm_json=$(aws ssm describe-instance-information --region "${AWS_REGION}" \
    --filters "Key=InstanceIds,Values=${CLIENT_INSTANCE_ID},${PEERING_INSTANCE_ID},${TGW_INSTANCE_ID}")
printf '%s\n' "${ssm_json}" > "${OUTPUT_DIR}/ssm_instances.json"
[ "$(printf '%s' "${ssm_json}" | jq '[.InstanceInformationList[] | select(.PingStatus == "Online")] | length')" -eq 3 ] || die "all instances must be SSM Online"
pass "ssm-online:3"

routes_json=$(aws ec2 describe-route-tables --region "${AWS_REGION}" --route-table-ids \
    "${CLIENT_ROUTE_TABLE_ID}" "${PEERING_ROUTE_TABLE_ID}" "${TGW_ROUTE_TABLE_ID}")
printf '%s\n' "${routes_json}" > "${OUTPUT_DIR}/route_tables.json"
"${PYTHON_BIN}" - "${OUTPUT_DIR}/route_tables.json" \
    "${CLIENT_ROUTE_TABLE_ID}" "${PEERING_ROUTE_TABLE_ID}" "${TGW_ROUTE_TABLE_ID}" \
    "${PEERING_CONNECTION_ID}" "${TRANSIT_GATEWAY_ID}" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    p = json.load(handle)
client, peering_rt, tgw_rt, pcx, tgw = sys.argv[2:]
tables = {t["RouteTableId"]: t["Routes"] for t in p["RouteTables"]}
def route(rt, cidr, target, value):
    return any(r.get("DestinationCidrBlock") == cidr and r.get(target) == value and r.get("State") == "active" for r in tables[rt])
checks = [
    route(client, "10.2.1.0/24", "VpcPeeringConnectionId", pcx),
    route(client, "10.2.2.0/24", "TransitGatewayId", tgw),
    route(peering_rt, "10.1.0.0/16", "VpcPeeringConnectionId", pcx),
    route(tgw_rt, "10.1.0.0/16", "TransitGatewayId", tgw),
]
if not all(checks):
    raise SystemExit(f"route contract failed: {checks}")
PY
pass "symmetric-route-contract"

sg_json=$(aws ec2 describe-security-groups --region "${AWS_REGION}" --group-ids "${SERVER_SECURITY_GROUP_ID}")
printf '%s\n' "${sg_json}" > "${OUTPUT_DIR}/server_security_group.json"
"${PYTHON_BIN}" - "${OUTPUT_DIR}/server_security_group.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    permissions = json.load(handle)["SecurityGroups"][0]["IpPermissions"]
def has(proto, start, end):
    return any(p.get("IpProtocol") == proto and p.get("FromPort") == start and p.get("ToPort") == end and
               any(r.get("CidrIp") == "10.1.1.0/24" for r in p.get("IpRanges", [])) for p in permissions)
if not (has("tcp", 5201, 5201) and has("udp", 5201, 5201) and has("tcp", 5202, 5202) and has("icmp", -1, -1)):
    raise SystemExit("security group benchmark port contract failed")
if any(p.get("FromPort") == 22 and p.get("IpProtocol") == "tcp" for p in permissions):
    raise SystemExit("SSH ingress is forbidden")
PY
pass "security-group-ports-no-ssh"

ssm_run() {
    local instance_id="$1" command="$2" label="$3"
    local parameters_file="${OUTPUT_DIR}/ssm/${label}_parameters.json"
    jq -n --arg command "${command}" '{commands:[$command]}' > "${parameters_file}"
    local command_id status invocation
    command_id=$(aws ssm send-command --region "${AWS_REGION}" --instance-ids "${instance_id}" \
        --document-name AWS-RunShellScript --parameters "file://${parameters_file}" \
        --query Command.CommandId --output text)
    status=Pending
    for _ in $(seq 1 180); do
        if invocation=$(aws ssm get-command-invocation --region "${AWS_REGION}" \
            --command-id "${command_id}" --instance-id "${instance_id}" 2>/dev/null); then
            status=$(printf '%s' "${invocation}" | jq -r .Status)
            case "${status}" in Success|Cancelled|TimedOut|Failed|Cancelling) break ;; esac
        fi
        sleep 1
    done
    printf '%s\n' "${invocation:-{}}" > "${OUTPUT_DIR}/ssm/${label}_invocation.json"
    [ "${status}" = Success ] || die "SSM ${label} failed:${status}"
}

for pair in "${PEERING_INSTANCE_ID}:b1" "${TGW_INSTANCE_ID}:b2"; do
    instance_id="${pair%%:*}"; label="${pair##*:}"
    ssm_run "${instance_id}" \
        "set -euo pipefail; test -s /var/lib/nt531/bootstrap.complete; test -x /opt/capstone/scripts/dut_server_setup.sh; sudo bash /opt/capstone/scripts/dut_server_setup.sh start_daemons ${INTERFACE}" \
        "${label}_runtime"
done
pass "server-bootstrap-and-daemons"

for target in "${PEERING_IP}" "${TGW_IP}"; do
    ping -n -c 10 -W 1 "${target}" >/dev/null || die "ICMP reachability:${target}"
    timeout 3 bash -c "</dev/tcp/${target}/5201" || die "TCP 5201:${target}"
    timeout 3 bash -c "</dev/tcp/${target}/5202" || die "TCP 5202:${target}"
done
pass "reachability-and-listeners"

original_mtu=$(ip link show dev "${INTERFACE}" | awk '/mtu/ {print $5; exit}')
trap 'sudo ip link set dev "${INTERFACE}" mtu "${original_mtu}" >/dev/null 2>&1 || true' EXIT
sudo ip link set dev "${INTERFACE}" mtu 9001
ssm_run "${PEERING_INSTANCE_ID}" "sudo bash /opt/capstone/scripts/dut_server_setup.sh set_mtu_9001 ${INTERFACE}" "b1_mtu9001"
ssm_run "${TGW_INSTANCE_ID}" "sudo bash /opt/capstone/scripts/dut_server_setup.sh set_mtu_9001 ${INTERFACE}" "b2_mtu9001"
ping -n -c 5 -M do -s 8973 "${PEERING_IP}" > "${OUTPUT_DIR}/mtu9001_peering.txt" || die "Peering jumbo-frame path"
ping -n -c 5 -M do -s 8973 "${TGW_IP}" > "${OUTPUT_DIR}/mtu9001_tgw.txt" || die "TGW jumbo-frame path"
sudo ip link set dev "${INTERFACE}" mtu "${original_mtu}"
ssm_run "${PEERING_INSTANCE_ID}" "sudo bash /opt/capstone/scripts/dut_server_setup.sh restore_original_mtu ${INTERFACE}" "b1_mtu_restore"
ssm_run "${TGW_INSTANCE_ID}" "sudo bash /opt/capstone/scripts/dut_server_setup.sh restore_original_mtu ${INTERFACE}" "b2_mtu_restore"
trap - EXIT
pass "path-mtu-9001"

driver=$(ethtool -i "${INTERFACE}" | awk -F': ' '$1 == "driver" {print $2}')
[ "${driver}" = ena ] || die "client network driver is not ENA:${driver}"
ssm_run "${PEERING_INSTANCE_ID}" \
    "set -euo pipefail; test \"\$(ethtool -i ${INTERFACE} | awk -F': ' '\''\$1 == \"driver\" {print \$2}'\'')\" = ena; sudo bash /opt/capstone/scripts/dut_server_setup.sh apply_xdp_native ${INTERFACE}" \
    "b1_xdp_native"
ssm_run "${PEERING_INSTANCE_ID}" \
    "sudo bash /opt/capstone/scripts/dut_server_setup.sh remove_xdp_native ${INTERFACE}" \
    "b1_xdp_remove"
pass "ena-and-xdp-native-driver-mode"

printf 'PREFLIGHT_RESULT scope=aws aws_verified=true pass=%s fail=0 output=%s\n' "${PASS_COUNT}" "${OUTPUT_DIR}"
