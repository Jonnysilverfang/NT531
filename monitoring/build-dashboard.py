"""Generate the provisioned host-metrics dashboard; no fabricated measurements."""
import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "nt531-prometheus"}
SELECT = 'nt531_phase="observability-demo"'

def panel(i, title, expr, unit, legend, x, y, description):
    return {
        "id": i, "type": "timeseries", "title": title,
        "description": description, "datasource": DS,
        "gridPos": {"h": 8, "w": 12, "x": x, "y": y},
        "targets": [{"refId": "A", "expr": expr, "legendFormat": legend}],
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
    }

panels = [{
    "id": 1, "type": "text", "title": "NT531 · Separate observability demo",
    "gridPos": {"h": 4, "w": 24, "x": 0, "y": 0},
    "options": {"mode": "markdown", "content":
        "Host metrics every 10 seconds. Use this dashboard to explain CPU and network load. "
        "RTT, TCP goodput and ENA allowance events remain in the raw experiment files. "
        "No data means no agent is reporting; it does not mean zero CPU or zero traffic. "
        "Keep collectors stopped during all 16 confirmatory RTT blocks."},
}]
panels.append(panel(2, "CPU busy by logical CPU",
    '100 * (1 - sum by (nt531_node, nt531_mode, cpu) '
    f'(rate(system_cpu_time{{{SELECT},state="idle"}}[1m])))',
    "percent", "{{nt531_node}} / {{nt531_mode}} / CPU {{cpu}}", 0, 4,
    "Busy includes user/system/softirq/iowait/steal. Inspect raw mpstat to distinguish causes."))
panels.append(panel(3, "Network interface traffic",
    '8 * sum by (nt531_node, nt531_mode, direction) '
    f'(rate(system_network_io{{{SELECT}}}[1m]))',
    "bps", "{{nt531_node}} / {{nt531_mode}} / {{direction}}", 12, 4,
    "Interface byte rate includes overhead and telemetry; it is not iperf3 payload goodput."))
panels.append(panel(4, "One-minute load average",
    f'system_cpu_load_average_1m{{{SELECT}}}',
    "short", "{{nt531_node}} / {{nt531_mode}}", 0, 12,
    "Runnable and uninterruptible tasks; not CPU utilization or a queue length in the AWS network."))
panels.append(panel(5, "Network drops reported by the OS",
    'sum by (nt531_node, nt531_mode, direction) '
    f'(rate(system_network_dropped{{{SELECT}}}[1m]))',
    "pps", "{{nt531_node}} / {{nt531_mode}} / {{direction}}", 12, 12,
    "OS interface drop counters; not the ENA allowance counters and not end-to-end packet loss."))

dashboard = {
    "uid": "nt531-host-demo", "title": "NT531 · Host observability demo",
    "tags": ["NT531", "observability-demo"], "schemaVersion": 40,
    "version": 1, "editable": False, "refresh": "10s", "timezone": "utc",
    "time": {"from": "now-15m", "to": "now"}, "panels": panels,
}
target = Path(__file__).parent / "grafana/dashboards/nt531-hosts.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(target)
