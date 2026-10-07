#!/usr/bin/env bash
# Run manually as ec2-user on A/B/C/D with the same future Unix timestamp.
# Does not change AWS routes. Verify Peering/TGW in AWS before choosing the label.
set -euo pipefail
mode=${1:?Usage: bash measure-tcp-fanin.sh peering_or_tgw start_epoch}
start=${2:?Supply the same future Unix timestamp on all four hosts}
[[ "$mode" == peering || "$mode" == tgw ]] || exit 2
[[ "$start" =~ ^[0-9]+$ ]] || exit 2
(( start > $(date +%s) + 5 )) || { echo 'Start time has passed or is too close. Choose a new shared time.'; exit 2; }
local_ip=$(ip -4 -o addr show dev ens5 scope global | awk '{split($4,a,"/"); print a[1]; exit}')
case "$local_ip" in
  10.10.10.212) node=a; role=sender; target=10.20.10.155; port=5201; pair=a-b ;;
  10.20.10.155) node=b; role=receiver; target=10.20.10.155; port=0; pair=a-c-d-to-b ;;
  10.30.10.212) node=c; role=sender; target=10.20.10.155; port=5202; pair=c-b ;;
  10.40.10.155) node=d; role=sender; target=10.20.10.155; port=5203; pair=d-b ;;
  *) echo 'Unexpected host IP'; exit 2 ;;
esac
[[ $(cat /sys/class/net/ens5/mtu) == 1500 ]] || { echo 'Set MTU to 1500 before measuring.'; exit 2; }
[[ $(timedatectl show -p NTPSynchronized --value) == yes ]] || { echo 'Clock is not synchronized.'; exit 2; }
for tool in iperf3 jq mpstat ethtool; do command -v "$tool" >/dev/null; done
if [[ "$role" == receiver ]]; then for listen_port in 5201 5202 5203; do systemctl is-active --quiet "nt531-iperf@$listen_port"; done; fi
mkdir -p ~/nt531-results
out=$(mktemp -d "$HOME/nt531-results/$mode-tcp-fanin-$node-$start-XXXXXX")
cpu_pid=''
cleanup() {
  if [[ -n "$cpu_pid" ]]; then kill "$cpu_pid" 2>/dev/null || true; wait "$cpu_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
{
  printf 'mode=%s\nscenario=fanin\nnode=%s\nrole=%s\npair=%s\npeer=%s\nstart_epoch=%s\n' "$mode" "$node" "$role" "$pair" "$target" "$start"
  echo "port=$port"
  echo 'Three sources to B; TCP P1 per source; omit 5s; measure 30s; five starts 45s apart; MTU 1500'
  date -u; hostname; iperf3 --version; ip link show ens5
  sysctl net.ipv4.tcp_congestion_control
  timedatectl show -p NTPSynchronized
} > "$out/metadata.txt" 2>&1
echo "READY $node: $(date -u -d "@$start" +%FT%TZ)"
echo "RESULTS: $out"
if [[ "$role" == receiver ]]; then
  sudo ethtool -S ens5 > "$out/ena-before.txt"
  LC_ALL=C TZ=UTC mpstat -P ALL 1 > "$out/cpu.txt" &
  cpu_pid=$!
  now=$(date +%s)
  (( start + 220 > now )) && sleep "$(( start + 220 - now ))"
  cleanup; cpu_pid=''
  sudo ethtool -S ens5 > "$out/ena-after.txt"
  date -u +%FT%T.%NZ > "$out/end.txt"
else
  printf 'run,sender_Gbps,receiver_Gbps,retransmits\n' > "$out/summary.csv"
  for run in 1 2 3 4 5; do
    planned=$((start + (run - 1) * 45))
    now=$(date +%s)
    if (( now > planned + 2 )); then
      echo "Missed shared start for run $run; results must be reviewed." | tee "$out/schedule-error.txt"
      exit 3
    fi
    (( planned > now )) && sleep "$((planned - now))"
    echo "RUN $run/5: $pair"
    echo "$planned" > "$out/run-$run-planned-epoch.txt"
    sudo ethtool -S ens5 > "$out/run-$run-ena-before.txt"
    LC_ALL=C TZ=UTC mpstat -P ALL 1 > "$out/run-$run-cpu.txt" &
    cpu_pid=$!
    date -u +%FT%T.%NZ > "$out/run-$run-start.txt"
    result=0
    iperf3 -c "$target" -p "$port" -P 1 -O 5 -t 30 -i 1 -J --get-server-output \
      > "$out/run-$run.json" 2> "$out/run-$run-stderr.txt" || result=$?
    echo "$result" > "$out/run-$run-exit-code.txt"
    date -u +%FT%T.%NZ > "$out/run-$run-end.txt"
    cleanup; cpu_pid=''
    sudo ethtool -S ens5 > "$out/run-$run-ena-after.txt"
    if [[ "$result" == 0 ]] && jq -e '.error == null and .end.sum_sent.bits_per_second != null and .end.sum_received.bits_per_second != null' "$out/run-$run.json" >/dev/null; then
      jq -r --argjson run "$run" '[$run, (.end.sum_sent.bits_per_second / 1e9), (.end.sum_received.bits_per_second / 1e9), .end.sum_sent.retransmits] | @csv' "$out/run-$run.json" >> "$out/summary.csv"
      tail -n 1 "$out/summary.csv"
    else
      echo "$run,NA,NA,NA" >> "$out/summary.csv"
      echo "Run $run failed; logs retained."
      exit 4
    fi
  done
  cat "$out/summary.csv"
fi
echo "DONE $node: $out"
