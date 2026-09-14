#!/usr/bin/env bash
# One-time AL2023 benchmark bootstrap. Failure leaves no readiness marker.
set -euo pipefail

readonly SOCKPERF_TAG="3.10"
readonly READY_FILE="/var/lib/nt531/bootstrap.complete"

exec > >(tee /var/log/nt531-bootstrap.log | logger -t nt531-bootstrap -s 2>/dev/console) 2>&1

sudo systemctl disable --now sshd
sudo dnf install -y \
    awscli bpftool clang cmake curl ethtool gcc gcc-c++ git iperf3 iproute \
    iptables-nft jq kernel-headers libbpf-devel libtool make openssl-devel \
    autoconf automake tar gzip

tmp_dir=$(mktemp -d /tmp/nt531-sockperf.XXXXXX)
trap 'rm -rf -- "${tmp_dir}"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 \
    "https://github.com/Mellanox/sockperf/archive/refs/tags/${SOCKPERF_TAG}.tar.gz" \
    --output "${tmp_dir}/sockperf.tar.gz"
tar -xzf "${tmp_dir}/sockperf.tar.gz" -C "${tmp_dir}"
pushd "${tmp_dir}/sockperf-${SOCKPERF_TAG}"
./autogen.sh
./configure --prefix=/usr/local
make -j"$(nproc)"
sudo make install
popd
sudo ldconfig

for required in aws bpftool clang ethtool ip iperf3 iptables jq sockperf; do
    command -v "${required}" >/dev/null
done
systemctl is-active --quiet amazon-ssm-agent

sudo install -d -m 0755 /var/lib/nt531 /opt/nt531/releases
{
    printf 'completed_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'sockperf_tag=%s\n' "${SOCKPERF_TAG}"
    rpm -q amazon-linux-repo-s3 amazon-ssm-agent awscli bpftool clang ethtool iperf3 iptables-libs kernel libbpf
    sockperf --version
} | sudo tee "${READY_FILE}"
sudo chmod 0444 "${READY_FILE}"
