#!/usr/bin/env bash
# Run as ec2-user on EACH existing Amazon Linux 2023 instance.
# Install missing tools only; leave MTU and benchmark execution explicit.
set -euo pipefail
source /etc/os-release
if [[ "${ID:-}" != "amzn" || "${VERSION_ID:-}" != "2023" ]]; then
  echo 'This script requires Amazon Linux 2023.' >&2
  exit 1
fi
if [[ "$EUID" -eq 0 ]]; then
  echo 'Run as ec2-user, without sudo; the installation step uses sudo.' >&2
  exit 1
fi
packages=()
command -v iperf3 >/dev/null 2>&1 || packages+=(iperf3)
command -v mpstat >/dev/null 2>&1 || packages+=(sysstat)
command -v jq >/dev/null 2>&1 || packages+=(jq)
command -v ethtool >/dev/null 2>&1 || packages+=(ethtool)
if (( ${#packages[@]} )); then
  sudo dnf install -y "${packages[@]}"
fi
mkdir -p "$HOME/nt531-results"
snapshot=$(mktemp "$HOME/nt531-results/environment-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.txt")
{
  date -u
  hostname
  cat /etc/os-release
  uname -r
  iperf3 --version
  ip -br addr
  ip link show
  ip route show
  sysctl net.ipv4.tcp_congestion_control
  mpstat 1 1
  ethtool -S ens5
} > "$snapshot" 2>&1
printf 'Environment saved to %s\n' "$snapshot"
