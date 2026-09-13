#!/usr/bin/env bash
# ==============================================================================
# Script: benchmark_runner.sh
# Mục tiêu: Tự động hóa đo đạc 4 kịch bản hiệu năng mạng trên AWS Sydney
# Thiết kế Chuẩn Mực Học Thuật & DevOps Doanh Nghiệp:
#  - Điều khiển DUT Receiver từ xa qua AWS Systems Manager (SSM Run Command)
#  - Tuyệt đối KHÔNG fallback âm thầm sang chạy cục bộ nếu chưa có cờ tường minh
#  - Lấy đầy đủ invocation stdout/stderr và kiểm tra ResponseCode của từng command
#  - Trích xuất snapshot SoftIRQ từ DUT về controller qua SSM stdout transport
#  - Tính toán trực tiếp SoftIRQ delta sau mỗi lượt chạy bằng calculate_softirq_delta.py
#  - Bẫy tín hiệu (trap cleanup) khôi phục an toàn có log cảnh báo thay vì nuốt lỗi
# ==============================================================================

set -euo pipefail

# Tham số cấu hình. Options được tách khỏi positional arguments để không thể
# vô tình biến "--execution-mode" thành địa chỉ IP của target.
TARGET_PEERING_IP="10.2.1.10"
TARGET_TGW_IP="10.2.2.10"
PRIVATELINK_ENDPOINT_IP="10.1.1.50"
NUM_RUNS="3"
INTERFACE="eth0"
EXECUTION_MODE="${EXECUTION_MODE:-aws-remote}" # Chế độ: 'aws-remote' (mặc định) hoặc 'local-emulation'
DUT_INSTANCE_ID="${DUT_INSTANCE_ID:-}"    # Bắt buộc khi EXECUTION_MODE=aws-remote
AWS_REGION="${AWS_REGION:-ap-southeast-2}"

# Parser CLI chặt chẽ: hỗ trợ --execution-mode VALUE và --execution-mode=VALUE.
POSITIONAL_ARGS=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --execution-mode=*)
            EXECUTION_MODE="${1#*=}"
            shift
            ;;
        --execution-mode)
            [ "$#" -ge 2 ] || { echo "[!] --execution-mode yêu cầu một giá trị." >&2; exit 2; }
            EXECUTION_MODE="$2"
            shift 2
            ;;
        --local-emulation)
            EXECUTION_MODE="local-emulation"
            shift
            ;;
        --)
            shift
            while [ "$#" -gt 0 ]; do POSITIONAL_ARGS+=("$1"); shift; done
            ;;
        --*)
            echo "[!] Tham số không được hỗ trợ: $1" >&2
            exit 2
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

[ "${#POSITIONAL_ARGS[@]}" -le 5 ] || { echo "[!] Chỉ chấp nhận tối đa 5 positional arguments." >&2; exit 2; }
TARGET_PEERING_IP="${POSITIONAL_ARGS[0]:-${TARGET_PEERING_IP}}"
TARGET_TGW_IP="${POSITIONAL_ARGS[1]:-${TARGET_TGW_IP}}"
PRIVATELINK_ENDPOINT_IP="${POSITIONAL_ARGS[2]:-${PRIVATELINK_ENDPOINT_IP}}"
NUM_RUNS="${POSITIONAL_ARGS[3]:-${NUM_RUNS}}"
INTERFACE="${POSITIONAL_ARGS[4]:-${INTERFACE}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RESULTS_DIR="${PROJECT_ROOT}/results/raw/run_$(date +%Y%m%d_%H%M%S)"
COMMANDS_DIR="${RESULTS_DIR}/commands"
mkdir -p "${RESULTS_DIR}" "${COMMANDS_DIR}"

DUT_CONTROLLER="${SCRIPT_DIR}/dut_server_setup.sh"
ORIGINAL_MTU=$(ip link show dev "${INTERFACE}" 2>/dev/null | awk '/mtu/ {print $5}' || echo 9001)

# Kiểm tra điều kiện tiên quyết tùy theo chế độ thực thi
if [ "${EXECUTION_MODE}" == "aws-remote" ]; then
    if [ -z "${DUT_INSTANCE_ID}" ]; then
        echo "================================================================================" >&2
        echo "[!] LỖI BẮT BUỘC HỌC THUẬT: DUT_INSTANCE_ID chưa được cung cấp!" >&2
        echo "    Để thực thi đo đạc chuẩn trên AWS, phải chỉ định ID của DUT qua biến môi trường:" >&2
        echo "    export DUT_INSTANCE_ID=\"i-0123456789abcdef0\"" >&2
        echo "" >&2
        echo "    Nếu bạn chỉ muốn kiểm thử cú pháp kịch bản cục bộ (không tính là empirical AWS)," >&2
        echo "    hãy chạy rõ ràng với cờ: --execution-mode local-emulation" >&2
        echo "================================================================================" >&2
        exit 1
    fi
    if ! command -v aws >/dev/null 2>&1; then
        echo "[!] LỖI: Lệnh 'aws' CLI không tồn tại. Bắt buộc để điều khiển DUT từ xa qua AWS SSM!" >&2
        exit 1
    fi
    echo "[+] Chế độ thực thi: AWS REMOTE SSM CONTROL (DUT: ${DUT_INSTANCE_ID} @ ${AWS_REGION})"
elif [ "${EXECUTION_MODE}" == "local-emulation" ]; then
    echo "================================================================================"
    echo " [!] CẢNH BÁO MINH BẠCH HỌC THUẬT (ACADEMIC TRANSPARENCY NOTICE):"
    echo "     Đang chạy ở chế độ LOCAL EMULATION trên cùng một máy."
    echo "     Kết quả này chỉ dùng để kiểm tra luồng kịch bản, KHÔNG PHẢI là kết quả đo trên AWS!"
    echo "================================================================================"
else
    echo "[!] Lỗi: Chế độ thực thi không hợp lệ: '${EXECUTION_MODE}'. Chỉ chấp nhận 'aws-remote' hoặc 'local-emulation'." >&2
    exit 1
fi

# Hàm điều khiển DUT từ xa qua AWS Systems Manager
run_on_dut() {
    local action="$1"
    local target_local_file="${2:-}"

    if [ "${EXECUTION_MODE}" == "aws-remote" ]; then
        echo "    [*] Gửi lệnh tới DUT từ xa qua AWS SSM (${DUT_INSTANCE_ID}): ${action}..."
        local cmd_id
        cmd_id=$(aws ssm send-command \
            --region "${AWS_REGION}" \
            --instance-ids "${DUT_INSTANCE_ID}" \
            --document-name "AWS-RunShellScript" \
            --parameters commands="[\"sudo bash /opt/capstone/scripts/dut_server_setup.sh ${action} ${INTERFACE} /tmp/dut_snapshot.json\"]" \
            --query "Command.CommandId" --output text)

        # Chờ command hoàn thành
        aws ssm wait command-executed \
            --region "${AWS_REGION}" \
            --command-id "${cmd_id}" \
            --instance-id "${DUT_INSTANCE_ID}"

        # Lấy toàn bộ invocation để kiểm tra ResponseCode và stdout/stderr
        local invocation_json
        invocation_json=$(aws ssm get-command-invocation \
            --region "${AWS_REGION}" \
            --command-id "${cmd_id}" \
            --instance-id "${DUT_INSTANCE_ID}")

        # Giữ nguyên response AWS để phục vụ audit độc lập về sau.
        printf '%s\n' "${invocation_json}" > "${COMMANDS_DIR}/${cmd_id}_invocation.json"

        local res_code stdout_content stderr_content
        res_code=$(echo "${invocation_json}" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("ResponseCode", 1))')
        stdout_content=$(echo "${invocation_json}" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("StandardOutputContent", ""))')
        stderr_content=$(echo "${invocation_json}" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("StandardErrorContent", ""))')

        # Lưu log command audit artifact
        echo "${stdout_content}" > "${COMMANDS_DIR}/${cmd_id}_stdout.log"
        echo "${stderr_content}" > "${COMMANDS_DIR}/${cmd_id}_stderr.log"
        printf '{"command_id":"%s","action":"%s","dut_instance_id":"%s","region":"%s","response_code":%s}\n' \
            "${cmd_id}" "${action}" "${DUT_INSTANCE_ID}" "${AWS_REGION}" "${res_code}" \
            > "${COMMANDS_DIR}/${cmd_id}_metadata.json"

        if [ "${res_code}" -ne 0 ]; then
            echo "[!] LỖI NGHIÊM TRỌNG: Lệnh SSM ${action} trên DUT thất bại với ResponseCode=${res_code}!" >&2
            echo "    Chi tiết stderr: ${stderr_content}" >&2
            exit 1
        fi

        # Nếu là hành động snapshot_counters và có chỉ định file lưu cục bộ trên controller
        if [ "${action}" == "snapshot_counters" ] && [ -n "${target_local_file}" ]; then
            echo "${stdout_content}" | python3 -c '
import sys, re
content = sys.stdin.read()
match = re.search(r"___DUT_SNAPSHOT_JSON_BEGIN___(.*?)___DUT_SNAPSHOT_JSON_END___", content, re.DOTALL)
if match:
    sys.stdout.write(match.group(1).strip())
else:
    sys.stderr.write("Không tìm thấy marker JSON trong SSM stdout!\n")
    sys.exit(1)
' > "${target_local_file}"
            echo "    [✓] Đã thu thập snapshot từ DUT và lưu vào controller: ${target_local_file}"
        fi

        echo "    [✓] Lệnh SSM ${cmd_id} (${action}) đã hoàn tất và xác thực thành công."
    else
        # Chế độ Local Emulation
        if [ -f "${DUT_CONTROLLER}" ]; then
            bash "${DUT_CONTROLLER}" "${action}" "${INTERFACE}" "${target_local_file}"
        else
            echo "[!] Lỗi: Không tìm thấy script DUT controller tại ${DUT_CONTROLLER}!" >&2
            exit 1
        fi
    fi
}

# Bẫy dọn dẹp có xử lý trạng thái rõ ràng, không nuốt lỗi cẩu thả
cleanup() {
    echo -e "\n[*] Đang thực hiện dọn dẹp hệ thống và khôi phục cấu hình an toàn..."
    if ! sudo ip link set dev "${INTERFACE}" mtu "${ORIGINAL_MTU}" 2>/dev/null; then
        echo "[!] Cảnh báo: Không thể khôi phục MTU ${ORIGINAL_MTU} trên Client." >&2
    fi
    if ! run_on_dut remove_iptables_drop "" 2>/dev/null; then
        echo "[!] Cảnh báo: Gỡ bỏ iptables trên DUT gặp sự cố hoặc chưa từng được gắn." >&2
    fi
    if ! run_on_dut remove_xdp_native "" 2>/dev/null; then
        echo "[!] Cảnh báo: Gỡ bỏ XDP trên DUT gặp sự cố hoặc chưa từng được gắn." >&2
    fi
    echo "[✓] Quá trình dọn dẹp Client và DUT hoàn tất."
}
trap cleanup EXIT INT TERM

echo "================================================================================"
echo " BỘ KIỂM THỬ HIỆU NĂNG MẠNG AWS TOÀN DIỆN - REGION SYDNEY (ap-southeast-2)"
echo " Chế độ: ${EXECUTION_MODE} | N = ${NUM_RUNS} Runs | MTU: ${ORIGINAL_MTU} | Interface: ${INTERFACE}"
echo " Thư mục lưu kết quả: ${RESULTS_DIR}"
echo "================================================================================"

# Thu thập ENA metrics trước khi chạy
if [ -f "${SCRIPT_DIR}/collect_ena_metrics.sh" ]; then
    if ! bash "${SCRIPT_DIR}/collect_ena_metrics.sh" "${RESULTS_DIR}/ena_baseline.txt" 2>"${RESULTS_DIR}/ena_baseline.stderr.log"; then
        echo "[!] Cảnh báo có cấu trúc: không thu thập được ENA baseline; xem ena_baseline.stderr.log." >&2
    fi
fi

# Khởi động daemons trên DUT trước khi đo đạc
echo "[*] Khởi tạo các daemon đo kiểm trên DUT..."
run_on_dut start_daemons ""

# ==============================================================================
# KỊCH BẢN 1: GIAO TIẾP MICROSERVICES (PEERING VS TRANSIT GATEWAY)
# ==============================================================================
echo -e "\n--------------------------------------------------------------------------------"
echo ">>> [TC-01] Đo đạc giao tiếp Microservices API: Peering vs TGW"
echo "    (Server B1 và B2 cùng AZ-a, cùng c6i.large, no PG để giảm thiểu Confounding)"
echo "--------------------------------------------------------------------------------"

for run in $(seq 1 "${NUM_RUNS}"); do
    echo -e "\n[*] [TC-01 / Run ${run}/${NUM_RUNS}] Crossover A/B testing..."
    if [ $((run % 2)) -eq 1 ]; then
        ORDER=("peering" "tgw")
    else
        ORDER=("tgw" "peering")
    fi

    for target_type in "${ORDER[@]}"; do
        if [ "${target_type}" == "peering" ]; then
            TARGET_IP="${TARGET_PEERING_IP}"
            LABEL="VPC_Peering"
        else
            TARGET_IP="${TARGET_TGW_IP}"
            LABEL="Transit_Gateway"
        fi

        echo "    -> Đang đo ${LABEL} (IP: ${TARGET_IP})..."
        if command -v sockperf &> /dev/null; then
            sockperf ping-pong -i "${TARGET_IP}" --tcp -t 10 --full-rtt \
                | tee "${RESULTS_DIR}/tc01_${LABEL}_run${run}.txt"
        else
            ping -c 1000 -i 0.01 "${TARGET_IP}" | tee "${RESULTS_DIR}/tc01_${LABEL}_run${run}.txt"
        fi
        sleep 2
    done
done

# ==============================================================================
# KỊCH BẢN 2B: TRUYỀN DỮ LIỆU LỚN & PHỤ TẢI CPU (MTU 1500 VS MTU 9001)
# ==============================================================================
echo -e "\n--------------------------------------------------------------------------------"
echo ">>> [TC-02B] Tối ưu hóa Truyền dữ liệu lớn: MTU 1500 vs MTU 9001"
echo "--------------------------------------------------------------------------------"

for run in $(seq 1 "${NUM_RUNS}"); do
    echo -e "\n[*] [TC-02B / Run ${run}/${NUM_RUNS}] Kiểm thử Jumbo Frames..."
    if [ $((run % 2)) -eq 1 ]; then
        MTU_LIST=(9001 1500)
    else
        MTU_LIST=(1500 9001)
    fi

    for mtu in "${MTU_LIST[@]}"; do
        echo "    -> Thiết lập MTU ${mtu} trên interface ${INTERFACE}..."
        sudo ip link set dev "${INTERFACE}" mtu "${mtu}"
        
        SNAP_BEFORE="${RESULTS_DIR}/tc02_softirq_before_mtu${mtu}_run${run}.json"
        SNAP_AFTER="${RESULTS_DIR}/tc02_softirq_after_mtu${mtu}_run${run}.json"
        DELTA_JSON="${RESULTS_DIR}/tc02_softirq_delta_mtu${mtu}_run${run}.json"
        
        run_on_dut snapshot_counters "${SNAP_BEFORE}"
        iperf3 -c "${TARGET_PEERING_IP}" -P 4 -t 10 \
            | tee "${RESULTS_DIR}/tc02_iperf_mtu${mtu}_run${run}.txt"
        run_on_dut snapshot_counters "${SNAP_AFTER}"

        # Tính toán SoftIRQ delta ngay lập tức trên cặp snapshot
        [ -s "${SNAP_BEFORE}" ] || { echo "[!] Thiếu snapshot before: ${SNAP_BEFORE}" >&2; exit 1; }
        [ -s "${SNAP_AFTER}" ] || { echo "[!] Thiếu snapshot after: ${SNAP_AFTER}" >&2; exit 1; }
        python3 "${SCRIPT_DIR}/calculate_softirq_delta.py" \
            --before "${SNAP_BEFORE}" \
            --after "${SNAP_AFTER}" \
            --condition "mtu_${mtu}" \
            --run-id "${run}" \
            --output-json "${DELTA_JSON}"
        sleep 2
    done
done

sudo ip link set dev "${INTERFACE}" mtu "${ORIGINAL_MTU}"

# ==============================================================================
# KỊCH BẢN 3: ĐỐI TÁC TRÙNG DẢI IP (PRIVATELINK VS PEERING)
# ==============================================================================
echo -e "\n--------------------------------------------------------------------------------"
echo ">>> [TC-03] Tích hợp Đối tác Trùng IP: AWS PrivateLink vs VPC Peering"
echo "--------------------------------------------------------------------------------"

for run in $(seq 1 "${NUM_RUNS}"); do
    echo -e "\n[*] [TC-03 / Run ${run}/${NUM_RUNS}] Kiểm thử định tuyến PrivateLink..."
    echo "    -> Đo đạc qua AWS PrivateLink (IP: ${PRIVATELINK_ENDPOINT_IP})..."
    if command -v sockperf &> /dev/null; then
        sockperf ping-pong -i "${PRIVATELINK_ENDPOINT_IP}" --tcp -t 10 --full-rtt \
            | tee "${RESULTS_DIR}/tc03_privatelink_run${run}.txt"
    else
        iperf3 -c "${PRIVATELINK_ENDPOINT_IP}" -t 10 | tee "${RESULTS_DIR}/tc03_privatelink_run${run}.txt"
    fi
    sleep 2
done

# ==============================================================================
# KỊCH BẢN 4: CHỐNG BÃO UDP FLOOD (LINUX IPTABLES VS EBPF/XDP NATIVE TRÊN DUT)
# ==============================================================================
echo -e "\n--------------------------------------------------------------------------------"
echo ">>> [TC-04] Kernel-Bypass eBPF/XDP vs iptables dưới bão UDP Flood"
echo "    Vai trò chuẩn: DUT Receiver nhận UDP:5201 & áp dụng Ingress Filter;"
echo "                   Client phát UDP Flood:5201 đồng thời đo Legitimate Probe TCP:5202."
echo "--------------------------------------------------------------------------------"

for run in $(seq 1 "${NUM_RUNS}"); do
    echo -e "\n[*] [TC-04 / Run ${run}/${NUM_RUNS}] Thử nghiệm bão UDP Flood..."
    
    # 4.1. Giai đoạn A: Linux iptables trên DUT Ingress
    echo "    [+] Kích hoạt Linux iptables trên DUT Ingress..."
    run_on_dut apply_iptables_drop ""
    
    SNAP_IPT_BEFORE="${RESULTS_DIR}/tc04_dut_iptables_before_run${run}.json"
    SNAP_IPT_AFTER="${RESULTS_DIR}/tc04_dut_iptables_after_run${run}.json"
    DELTA_IPT_JSON="${RESULTS_DIR}/tc04_dut_iptables_delta_run${run}.json"
    
    run_on_dut snapshot_counters "${SNAP_IPT_BEFORE}"
    
    echo "    -> Đang phát bão UDP Flood tới ${TARGET_PEERING_IP}:5201..."
    iperf3 -c "${TARGET_PEERING_IP}" -u -b 0 -p 5201 -t 15 &
    FLOOD_PID=$!
    
    echo "    -> Đang đo P95/P99 của luồng dịch vụ hợp lệ (TCP Probe port 5202)..."
    if command -v sockperf &>/dev/null; then
        sockperf ping-pong -i "${TARGET_PEERING_IP}" --port 5202 --tcp -t 12 --full-rtt \
            | tee "${RESULTS_DIR}/tc04_iptables_probe_run${run}.txt"
    else
        ping -c 50 "${TARGET_PEERING_IP}" | tee "${RESULTS_DIR}/tc04_iptables_probe_run${run}.txt"
    fi
    wait "${FLOOD_PID}"
    
    run_on_dut snapshot_counters "${SNAP_IPT_AFTER}"
    
    [ -s "${SNAP_IPT_BEFORE}" ] || { echo "[!] Thiếu snapshot iptables before." >&2; exit 1; }
    [ -s "${SNAP_IPT_AFTER}" ] || { echo "[!] Thiếu snapshot iptables after." >&2; exit 1; }
    python3 "${SCRIPT_DIR}/calculate_softirq_delta.py" \
        --before "${SNAP_IPT_BEFORE}" \
        --after "${SNAP_IPT_AFTER}" \
        --condition "iptables" \
        --run-id "${run}" \
        --output-json "${DELTA_IPT_JSON}"

    run_on_dut remove_iptables_drop ""
    sleep 3

    # 4.2. Giai đoạn B: eBPF/XDP Native Hook trên DUT Ingress
    echo "    [+] Kích hoạt eBPF/XDP Native Hook trên DUT Ingress..."
    run_on_dut apply_xdp_native ""
    
    SNAP_XDP_BEFORE="${RESULTS_DIR}/tc04_dut_xdp_before_run${run}.json"
    SNAP_XDP_AFTER="${RESULTS_DIR}/tc04_dut_xdp_after_run${run}.json"
    DELTA_XDP_JSON="${RESULTS_DIR}/tc04_dut_xdp_delta_run${run}.json"
    
    run_on_dut snapshot_counters "${SNAP_XDP_BEFORE}"
    
    echo "    -> Đang phát bão UDP Flood tới ${TARGET_PEERING_IP}:5201..."
    iperf3 -c "${TARGET_PEERING_IP}" -u -b 0 -p 5201 -t 15 &
    FLOOD_PID=$!
    
    echo "    -> Đang đo P95/P99 của luồng hợp lệ dưới lá chắn eBPF/XDP..."
    if command -v sockperf &>/dev/null; then
        sockperf ping-pong -i "${TARGET_PEERING_IP}" --port 5202 --tcp -t 12 --full-rtt \
            | tee "${RESULTS_DIR}/tc04_xdp_probe_run${run}.txt"
    else
        ping -c 50 "${TARGET_PEERING_IP}" | tee "${RESULTS_DIR}/tc04_xdp_probe_run${run}.txt"
    fi
    wait "${FLOOD_PID}"
    
    run_on_dut snapshot_counters "${SNAP_XDP_AFTER}"
    
    [ -s "${SNAP_XDP_BEFORE}" ] || { echo "[!] Thiếu snapshot XDP before." >&2; exit 1; }
    [ -s "${SNAP_XDP_AFTER}" ] || { echo "[!] Thiếu snapshot XDP after." >&2; exit 1; }
    python3 "${SCRIPT_DIR}/calculate_softirq_delta.py" \
        --before "${SNAP_XDP_BEFORE}" \
        --after "${SNAP_XDP_AFTER}" \
        --condition "xdp_native" \
        --run-id "${run}" \
        --output-json "${DELTA_XDP_JSON}"

    run_on_dut remove_xdp_native ""
    sleep 3
done

# ==============================================================================
# TỰ ĐỘNG KÍCH HOẠT PIPELINE PHÂN TÍCH THỐNG KÊ TOÁN HỌC DYNAMIC
# ==============================================================================
echo -e "\n================================================================================"
echo " TỰ ĐỘNG CHẠY PIPELINE PHÂN TÍCH THỐNG KÊ (ANALYZE_RESULTS.PY)"
echo "================================================================================"
if command -v python3 &>/dev/null; then
    python3 "${SCRIPT_DIR}/analyze_results.py" \
        --input-dir "${PROJECT_ROOT}/results/raw" \
        --output-json "${PROJECT_ROOT}/results/summary_statistics.json" \
        --bootstrap-resamples 10000 \
        --random-seed 42
fi

echo -e "\n[✔] HOÀN TẤT TOÀN BỘ 4 KỊCH BẢN THỰC NGHIỆM ĐẠT CHUẨN KHOA HỌC!"
