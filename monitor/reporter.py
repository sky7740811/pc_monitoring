"""Detailed session report generator — reads NDJSON, outputs HTML."""
import json
import os
import statistics as stat
from datetime import datetime


def generate(raw_path: str, start_time: float, duration: str, summary: dict, logs: list, top5_cpu: list, top5_ram: list, top5_gpu: list) -> str | None:
    if not raw_path or not os.path.exists(raw_path):
        return None

    log_dir = os.path.dirname(raw_path)
    fname = os.path.basename(raw_path).replace('raw_', 'report_').replace('.ndjson', '.html')
    out_path = os.path.join(log_dir, fname)

    rows: list[dict] = []
    with open(raw_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not rows:
        return None

    cpu_vals = [r['cpu'] for r in rows]
    gpu_vals = [r['gpu'] for r in rows]
    gt_vals = [r['gt'] for r in rows]
    ram_vals = [r['ram'] for r in rows]

    # Bottleneck timeline
    timeline_rows = ''
    prev_bn = ''
    for r in rows:
        cpu, gpu = r['cpu'], r['gpu']
        bn = ''
        if gpu > 90 and cpu < 60:
            bn = 'GPU_BOT'
        elif cpu > 85 and gpu < 70:
            bn = 'CPU_BOT'
        t_str = datetime.fromtimestamp(start_time + r['t']).strftime('%H:%M:%S') if start_time else f'{r["t"]}s'
        if bn and bn != prev_bn:
            icon = '🔴' if bn == 'GPU_BOT' else '🟡'
            timeline_rows += f'<tr><td>{t_str}</td><td>{icon} {bn}</td></tr>\n'
        prev_bn = bn

    # Anomalies
    anomaly_rows = ''
    for i in range(1, len(rows)):
        prev, cur = rows[i-1], rows[i]
        dt = cur['t'] - prev['t']
        anomalies = []
        if cur['cpu'] - prev['cpu'] > 30:
            anomalies.append(f'CPU {prev["cpu"]}% → {cur["cpu"]}% ({int(cur["cpu"]-prev["cpu"])}p 급등, {dt:.0f}초)')
        if cur['gt'] - prev['gt'] > 5:
            anomalies.append(f'GPU 온도 {prev["gt"]}°C → {cur["gt"]}°C (+{int(cur["gt"]-prev["gt"])}°C)')
        if prev['gpu'] > 80 and cur['gpu'] < 20:
            anomalies.append(f'GPU 사용률 {prev["gpu"]}% → {cur["gpu"]}% (게임 종료 추정)')
        if anomalies:
            t_str = datetime.fromtimestamp(start_time + cur['t']).strftime('%H:%M:%S') if start_time else f'{cur["t"]}s'
            for a in anomalies:
                anomaly_rows += f'<tr><td>{t_str}</td><td>{a}</td></tr>\n'

    # Load zones
    def zone_label(v):
        return '🔴 HIGH' if v > 70 else '🟡 MED' if v > 30 else '🟢 LOW'

    def zone_cpu(v):
        return '🔴' if v > 70 else '🟡' if v > 30 else '🟢'

    zones = []
    cur_zone = None
    zone_start = 0
    for i, r in enumerate(rows):
        z = zone_label(r['cpu'])
        if z != cur_zone:
            if cur_zone is not None:
                zones.append((cur_zone, rows[zone_start]['t'], rows[i-1]['t']))
            cur_zone = z
            zone_start = i
    if cur_zone is not None:
        zones.append((cur_zone, rows[zone_start]['t'], rows[-1]['t']))

    zone_rows = ''
    for z, t1, t2 in zones:
        t1_str = datetime.fromtimestamp(start_time + t1).strftime('%H:%M:%S') if start_time else f'{t1:.0f}s'
        t2_str = datetime.fromtimestamp(start_time + t2).strftime('%H:%M:%S') if start_time else f'{t2:.0f}s'
        dur = round(t2 - t1, 1)
        zone_rows += f'<tr><td>{z}</td><td>{t1_str} ~ {t2_str}</td><td>{dur}s</td></tr>\n'

    # Top5 HTML
    def top5_html(items, label):
        if not items:
            return ''
        h = f'<h2>Top 5 {label}</h2><table><tr><th>#</th><th>Process</th><th>Share</th></tr>'
        for i, (n, v) in enumerate(items, 1):
            h += f'<tr><td>{i}</td><td>{n}</td><td>{v}%</td></tr>'
        h += f'<tr style="opacity:.4"><td></td><td>Total</td><td>{sum(v for _,v in items)}%</td></tr></table>'
        return h

    # Chart.js timeline
    chart_labels = json.dumps([f"{r['t']:.0f}s" for r in rows], ensure_ascii=False)
    chart_cpu = json.dumps([r['cpu'] for r in rows])
    chart_gpu = json.dumps([r['gpu'] for r in rows])
    chart_gt = json.dumps([r['gt'] for r in rows])

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>Detailed Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:#080c14;color:#d0d5df;padding:24px;max-width:960px;margin:0 auto}}
h1{{font-size:1.3rem;color:#e8ecf4;margin-bottom:4px}}
.sub{{opacity:.4;font-size:.8rem;margin-bottom:16px}}
h2{{font-size:.9rem;color:#8892a0;margin:16px 0 8px;letter-spacing:.5px}}
table{{width:100%;border-collapse:collapse;font-size:.8rem;margin-bottom:8px}}
th,td{{padding:5px 10px;text-align:left;border-bottom:1px solid rgba(255,255,255,.04)}}
th{{color:#8892a0;font-weight:600;font-size:.7rem;letter-spacing:.5px}}
.summary td:first-child{{opacity:.5}}
.summary td:nth-child(2){{font-weight:600;color:#e8ecf4}}
.chart-wr{{height:200px;margin:12px 0 20px}}
</style></head>
<body>
<h1>Detailed Session Report</h1>
<p class="sub">{duration}</p>

<h2>1. Session Overview</h2>
<table class="summary">
<tr><td>CPU</td><td>avg {stat.mean(cpu_vals):.1f}% / max {max(cpu_vals):.0f}%</td></tr>
<tr><td>GPU</td><td>avg {stat.mean(gpu_vals):.1f}% / max {max(gpu_vals):.0f}%</td></tr>
<tr><td>GPU Temp</td><td>avg {stat.mean(gt_vals):.1f}°C / max {max(gt_vals):.0f}°C</td></tr>
<tr><td>RAM</td><td>avg {stat.mean(ram_vals):.1f}%</td></tr>
</table>

<h2>2. Timeline Chart</h2>
<div class="chart-wr"><canvas id="chart"></canvas></div>
<script>
new Chart(document.getElementById('chart'), {{
  type:'line', data:{{
    labels:{chart_labels},
    datasets:[
      {{label:'CPU',data:{chart_cpu},borderColor:'#00d4ff',borderWidth:1.5,fill:false,tension:.3,pointRadius:0,yAxisID:'y'}},
      {{label:'GPU',data:{chart_gpu},borderColor:'#ff6b35',borderWidth:1.5,fill:false,tension:.3,pointRadius:0,yAxisID:'y'}},
      {{label:'Temp',data:{chart_gt},borderColor:'#ef4444',borderWidth:1,borderDash:[3,3],fill:false,tension:.3,pointRadius:0,yAxisID:'y1'}},
    ]}},
    options:{{
      responsive:true,maintainAspectRatio:false,animation:false,
      scales:{{
        x:{{display:true,ticks:{{maxTicksLimit:10,color:'#555',font:{{size:10}}}}}},
        y:{{min:0,max:100,position:'left',title:{{display:true,text:'%',color:'#555'}}}},
        y1:{{min:0,max:100,position:'right',title:{{display:true,text:'°C',color:'#555'}},grid:{{display:false}}}},
      }},
      plugins:{{legend:{{display:true,labels:{{color:'#8892a0',font:{{size:11}},boxWidth:12}}}}}}
    }}
}});
</script>

{"<h2>3. Bottleneck Timeline</h2><table><tr><th>Time</th><th>Event</th></tr>" + timeline_rows + "</table>" if timeline_rows else ""}

{"<h2>4. Anomaly Detection</h2><table><tr><th>Time</th><th>Event</th></tr>" + anomaly_rows + "</table>" if anomaly_rows else ""}

{"<h2>5. Load Zones</h2><table><tr><th>Zone</th><th>Period</th><th>Duration</th></tr>" + zone_rows + "</table>" if zone_rows else ""}

{top5_html(top5_cpu, 'CPU')}
{top5_html(top5_ram, 'RAM')}
{top5_html(top5_gpu, 'GPU')}

</body></html>'''

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path
