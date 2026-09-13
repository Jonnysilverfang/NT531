// SPDX-License-Identifier: GPL-2.0
/*
 * xdp_packet_filter.c - High-Performance eBPF/XDP Ingress Engine on AWS ENA Driver
 * 
 * Chuẩn hóa:
 *  - Sử dụng BTF-defined maps (SEC(".maps")) tương thích libbpf / Kernel 5.10+
 *  - Xử lý kiểm tra biên đầy đủ (Bounds check, IHL validation >= 5, IP fragments check)
 *  - Thu thập số liệu Ingress tại driver RX hook trước khi cấp phát sk_buff
 *  - Chú ý ENA Native XDP: Hoạt động tối ưu ở Standard MTU 1500 (single-buffer)
 */

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#define TARGET_BENCHMARK_PORT 5201

/*
 * Cấu trúc BTF Map chuẩn hiện đại (thay thế struct bpf_map_def legacy)
 * Sử dụng BPF_MAP_TYPE_PERCPU_ARRAY tránh tranh chấp cache line giữa các vCPU
 */
struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __type(key, __u32);
    __type(value, __u64);
    __uint(max_entries, 4);
} xdp_stats_map SEC(".maps");

/* Config map điều khiển bật/tắt chế độ lọc động */
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __type(key, __u32);
    __type(value, __u32);
    __uint(max_entries, 2);
} xdp_config_map SEC(".maps");

static __always_inline void record_stats(__u32 index, __u64 bytes) {
    __u64 *val = bpf_map_lookup_elem(&xdp_stats_map, &index);
    if (val) {
        *val += 1;
    }
    __u32 bytes_idx = 2;
    __u64 *byte_val = bpf_map_lookup_elem(&xdp_stats_map, &bytes_idx);
    if (byte_val) {
        *byte_val += bytes;
    }
}

SEC("xdp")
int xdp_network_optimizer(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data     = (void *)(long)ctx->data;
    __u64 packet_len = (__u64)(data_end - data);

    // 1. Kiểm tra Ethernet Header
    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) {
        return XDP_PASS;
    }

    // Chỉ kiểm tra gói tin IPv4
    if (eth->h_proto != bpf_htons(ETH_P_IP)) {
        return XDP_PASS;
    }

    // 2. Kiểm tra IPv4 Header
    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) {
        return XDP_PASS;
    }

    // Kiểm tra tính hợp lệ của Header Length (IHL tối thiểu 5 words = 20 bytes)
    if (ip->ihl < 5) {
        return XDP_PASS;
    }

    void *ip_end = (void *)((__u32 *)ip + ip->ihl);
    if (ip_end > data_end) {
        return XDP_PASS;
    }

    // Kiểm tra phân mảnh (Bỏ qua các mảnh IP tiếp theo vì không chứa L4 header)
    if (ip->frag_off & bpf_htons(IP_OFFSET | IP_MF)) {
        return XDP_PASS;
    }

    // Đọc trạng thái cấu hình từ BPF Map
    __u32 cfg_key = 0;
    __u32 *filter_enabled = bpf_map_lookup_elem(&xdp_config_map, &cfg_key);

    // 3. Phân tích Transport Layer (TCP / UDP)
    if (ip->protocol == IPPROTO_TCP) {
        struct tcphdr *tcp = (void *)ip_end;
        if ((void *)(tcp + 1) > data_end) {
            return XDP_PASS;
        }

        if (tcp->dest == bpf_htons(TARGET_BENCHMARK_PORT)) {
            record_stats(0, packet_len); // Key 0: Pass packets
            return XDP_PASS;
        }
    } else if (ip->protocol == IPPROTO_UDP) {
        struct udphdr *udp = (void *)ip_end;
        if ((void *)(udp + 1) > data_end) {
            return XDP_PASS;
        }

        // Kịch bản Stress-test: Hủy gói tin UDP Ingress tại driver ENA
        if (filter_enabled && *filter_enabled == 1) {
            if (udp->dest == bpf_htons(TARGET_BENCHMARK_PORT)) {
                record_stats(1, packet_len); // Key 1: Drop packets
                return XDP_DROP; // Bỏ qua sk_buff, hủy tức thì tại RX Ring
            }
        }
    }

    record_stats(0, packet_len);
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
