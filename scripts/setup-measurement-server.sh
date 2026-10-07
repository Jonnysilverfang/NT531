#!/usr/bin/env bash
# Run as ec2-user. Installs tools, then starts idle iperf3 listeners (no test load).
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bash "$script_dir/prepare-measurement.sh"
private_ip=$(ip -4 -o addr show dev ens5 scope global | awk '{split($4,a,"/"); print a[1]; exit}')
case "$private_ip" in
  10.10.10.212|10.20.10.155|10.30.10.212|10.40.10.155) ;;
  *) echo "Unexpected private IP; refusing setup: $private_ip" >&2; exit 1 ;;
esac
iperf_bin=$(command -v iperf3)
sudo tee /etc/systemd/system/nt531-iperf@.service >/dev/null <<EOF
[Unit]
Description=NT531 iperf3 listener on private IP port %i
Wants=network-online.target
After=network-online.target

[Service]
User=ec2-user
ExecStart=$iperf_bin -s -B $private_ip -p %i
Restart=on-failure
RestartSec=3
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
for port in 5201 5202 5203; do
  sudo systemctl enable --now "nt531-iperf@$port.service"
  sleep 1
  sudo systemctl is-active --quiet "nt531-iperf@$port.service"
done
ss -ltn | grep -E ':520[123][[:space:]]'
printf 'Ready: %s, TCP 5201/5202/5203. MTU unchanged.\n' "$private_ip"
