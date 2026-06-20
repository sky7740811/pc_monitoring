"""Detailed session report — NDJSON -> HTML avec analyse par composant."""
import json, os, statistics as stat
from datetime import datetime


def _threshold(val, warn, danger):
    return 'danger' if val > danger else 'warning' if val > warn else 'good'


def _fmt(v):
    return f'{v:.1f}'


def generate(raw_path, start_time, duration, summary, logs, top5_cpu, top5_ram, top5_gpu):
    if not raw_path or not os.path.exists(raw_path):
        return None

    log_dir = os.path.abspath(os.path.join(os.path.dirname(raw_path), '..'))
    fname = 'report_' + os.path.basename(raw_path).replace('.ndjson', '.html')
    out_path = os.path.join(log_dir, fname)

    rows = []
    with open(raw_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except: continue
    if not rows: return None

    cpu_vals = [r['cpu'] for r in rows]
    gpu_vals = [r['gpu'] for r in rows]
    gt_vals = [r['gt'] for r in rows]
    ram_vals = [r['ram'] for r in rows]

    cpu_avg, cpu_max = stat.mean(cpu_vals), max(cpu_vals)
    gpu_avg, gpu_max = stat.mean(gpu_vals), max(gpu_vals)
    gt_avg, gt_max = stat.mean(gt_vals), max(gt_vals)
    ram_avg = stat.mean(ram_vals)

    # Per-component status
    cpu_status = _threshold(cpu_avg, 70, 90)
    gpu_status = _threshold(gpu_avg, 80, 95)
    gt_status = _threshold(gt_max, 75, 85)
    ram_status = _threshold(ram_avg, 70, 90)

    def status_html(label, st, detail_lines):
        icons = {'good': '\u2705', 'warning': '\u26a0\ufe0f', 'danger': '\U0001f525'}
        ico = icons.get(st, '\u2139\ufe0f')
        lines = ''.join(f'<tr><td>{l}</td></tr>' for l in detail_lines)
        return f'<div class="comp {st}"><div class="comp-h">{ico} {label}</div><table class="comp-d">{lines}</table></div>'

    # Build detail lines
    cpu_lines = [f'Average: {_fmt(cpu_avg)}% / Peak: {_fmt(cpu_max)}%']
    if cpu_max > 90: cpu_lines.append(f'\u26a0\ufe0f CPU peaked at {_fmt(cpu_max)}% - high load')
    if cpu_max < 30: cpu_lines.append(f'\U0001f7e2 CPU was mostly idle (max {_fmt(cpu_max)}%)')
    else: cpu_lines.append(f'\U0001f7e1 CPU load range: {_fmt(min(cpu_vals))}% ~ {_fmt(cpu_max)}%')

    gpu_lines = [f'Average: {_fmt(gpu_avg)}% / Peak: {_fmt(gpu_max)}%']
    gpu_lines.append(f'Temp: avg {_fmt(gt_avg)}\u00b0C / peak {_fmt(gt_max)}\u00b0C')
    if gt_max > 85: gpu_lines.append(f'\U0001f525 GPU temperature reached {_fmt(gt_max)}\u00b0C - danger zone')
    elif gt_max > 75: gpu_lines.append(f'\u26a0\ufe0f GPU temperature peaked at {_fmt(gt_max)}\u00b0C')
    else: gpu_lines.append(f'\U0001f7e2 GPU temperature stable (max {_fmt(gt_max)}\u00b0C)')
    if gpu_max > 90: gpu_lines.append(f'\u26a0\ufe0f GPU was near full utilization ({_fmt(gpu_max)}%)')

    ram_lines = [f'Average: {_fmt(ram_avg)}%']
    if ram_avg > 85: ram_lines.append(f'\u26a0\ufe0f High memory pressure')
    elif ram_avg < 50: ram_lines.append(f'\U0001f7e2 Ample memory available')
    else: ram_lines.append(f'\U0001f7e1 Moderate memory usage')

    # Event log summary
    warn_count = sum(1 for e in logs if e['type'] == 'warning')
    danger_count = sum(1 for e in logs if e['type'] == 'danger')
    idle_count = sum(1 for e in logs if e['type'] == 'idle')

    event_rows = ''
    for e in logs[-30:]:
        cls = 'l-w' if e['type'] == 'warning' else 'l-d' if e['type'] == 'danger' else 'l-i' if e['type'] == 'idle' else ''
        event_rows += f'<tr class="{cls}"><td>{e["time"]}</td><td>{e["icon"]}</td><td>{e["msg"]}</td></tr>\n'

    # Bottleneck timeline
    prev_bn = ''
    bn_rows = ''
    for r in rows:
        bn = ''
        if r['gpu'] > 90 and r['cpu'] < 60: bn = 'GPU_BOT'
        elif r['cpu'] > 85 and r['gpu'] < 70: bn = 'CPU_BOT'
        t_str = datetime.fromtimestamp(start_time + r['t']).strftime('%H:%M:%S') if start_time else f'{r["t"]:.0f}s'
        if bn and bn != prev_bn:
            icon = '\U0001f534' if bn == 'GPU_BOT' else '\U0001f7e1'
            bn_rows += f'<tr><td>{t_str}</td><td>{icon} {bn}</td></tr>\n'
        prev_bn = bn

    # Anomalies
    anom_rows = ''
    for i in range(1, len(rows)):
        p, c = rows[i-1], rows[i]
        anoms = []
        if c['cpu'] - p['cpu'] > 30:
            anoms.append(f'CPU {p["cpu"]:.0f}% \u2192 {c["cpu"]:.0f}% (+{c["cpu"]-p["cpu"]:.0f}p)')
        if c['gt'] - p['gt'] > 5:
            anoms.append(f'Temp {p["gt"]:.0f}\u00b0C \u2192 {c["gt"]:.0f}\u00b0C (+{c["gt"]-p["gt"]:.0f}\u00b0C)')
        if p['gpu'] > 80 and c['gpu'] < 20:
            anoms.append(f'GPU usage dropped {p["gpu"]:.0f}% \u2192 {c["gpu"]:.0f}% (session end)')
        if anoms:
            t_str = datetime.fromtimestamp(start_time + c['t']).strftime('%H:%M:%S') if start_time else f'{c["t"]:.0f}s'
            for a in anoms:
                anom_rows += f'<tr><td>{t_str}</td><td>{a}</td></tr>\n'

    # Load zones
    def zlabel(v): return 'HIGH' if v > 70 else 'MED' if v > 30 else 'LOW'
    zones, cur_zone, z_start = [], None, 0
    for i, r in enumerate(rows):
        z = zlabel(r['cpu'])
        if z != cur_zone:
            if cur_zone is not None: zones.append((cur_zone, z_start, i-1))
            cur_zone, z_start = z, i
    if cur_zone is not None: zones.append((cur_zone, z_start, len(rows)-1))

    zone_rows = ''
    for z, s, e in zones:
        t1 = datetime.fromtimestamp(start_time + rows[s]['t']).strftime('%H:%M:%S') if start_time else f'{rows[s]["t"]:.0f}s'
        t2 = datetime.fromtimestamp(start_time + rows[e]['t']).strftime('%H:%M:%S') if start_time else f'{rows[e]["t"]:.0f}s'
        icons = {'HIGH': '\U0001f534', 'MED': '\U0001f7e1', 'LOW': '\U0001f7e2'}
        zone_rows += f'<tr><td>{icons.get(z,"")} {z}</td><td>{t1} ~ {t2}</td><td>{rows[e]["t"]-rows[s]["t"]:.0f}s</td></tr>\n'

    def top5_html(items, label):
        if not items: return ''
        h = f'<h2>Top 5 {label}</h2><table><tr><th>#</th><th>Process</th><th>Share</th></tr>'
        for i, (n, v) in enumerate(items, 1):
            cls = ' class="warn"' if v > 50 else ''
            h += f'<tr{cls}><td>{i}</td><td>{n}</td><td>{v}%</td></tr>'
        h += f'<tr style="opacity:.4"><td></td><td>Total</td><td>{sum(v for _,v in items):.1f}%</td></tr></table>'
        return h

    c_labels = json.dumps([f'{r["t"]:.0f}s' for r in rows], ensure_ascii=False)
    c_cpu = json.dumps([r['cpu'] for r in rows])
    c_gpu = json.dumps([r['gpu'] for r in rows])
    c_gt = json.dumps([r['gt'] for r in rows])

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>Detailed Session Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:#080c14;color:#d0d5df;padding:24px;max-width:960px;margin:0 auto}}
h1{{font-size:1.3rem;color:#e8ecf4;margin-bottom:4px}}
h2{{font-size:.9rem;color:#8892a0;margin:20px 0 8px;letter-spacing:.5px}}
.sub{{opacity:.4;font-size:.8rem;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;font-size:.8rem;margin-bottom:8px}}
th,td{{padding:5px 10px;text-align:left;border-bottom:1px solid rgba(255,255,255,.04)}}
th{{color:#8892a0;font-weight:600;font-size:.7rem;letter-spacing:.5px}}
.chart-wr{{height:200px;margin:12px 0}}
.comp{{border-radius:8px;padding:10px 12px;margin-bottom:6px;font-size:.8rem}}
.comp.good{{background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.12)}}
.comp.warning{{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.12)}}
.comp.danger{{background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.12)}}
.comp-h{{font-weight:600;font-size:.85rem;margin-bottom:4px}}
.comp-d td{{border:none;padding:1px 0;font-size:.75rem;opacity:.7}}
.warn{{color:#ef4444}}
.l-w td{{border-left:2px solid rgba(245,158,11,.3)}}
.l-d td{{border-left:2px solid rgba(239,68,68,.3)}}
.l-i td{{border-left:2px solid rgba(168,130,255,.3)}}
</style></head>
<body>
<h1>Detailed Session Report</h1>
<p class="sub">{duration}</p>

<h2>1. Component Status</h2>
{status_html('CPU', cpu_status, cpu_lines)}
{status_html('GPU', gpu_status, gpu_lines)}
{status_html('RAM', ram_status, ram_lines)}

<h2>2. Timeline Chart</h2>
<div class="chart-wr"><canvas id="chart"></canvas></div>
<script>
new Chart(document.getElementById('chart'), {{
  type:'line', data:{{
    labels:{c_labels},
    datasets:[
      {{label:'CPU',data:{c_cpu},borderColor:'#00d4ff',borderWidth:1.5,fill:false,tension:.3,pointRadius:0,yAxisID:'y'}},
      {{label:'GPU',data:{c_gpu},borderColor:'#ff6b35',borderWidth:1.5,fill:false,tension:.3,pointRadius:0,yAxisID:'y'}},
      {{label:'Temp',data:{c_gt},borderColor:'#ef4444',borderWidth:1,borderDash:[3,3],fill:false,tension:.3,pointRadius:0,yAxisID:'y1'}},
    ]}},
    options:{{
      responsive:true,maintainAspectRatio:false,animation:false,
      scales:{{
        x:{{display:true,ticks:{{maxTicksLimit:10,color:'#555',font:{{size:10}}}}}},
        y:{{min:0,max:100,position:'left',title:{{display:true,text:'%',color:'#555'}}}},
        y1:{{min:0,max:100,position:'right',title:{{display:true,text:'\u00b0C',color:'#555'}},grid:{{display:false}}}},
      }},
      plugins:{{legend:{{display:true,labels:{{color:'#8892a0',font:{{size:11}},boxWidth:12}}}}}}
    }}
}});
</script>

{"<h2>3. Bottleneck Timeline</h2><table><tr><th>Time</th><th>Event</th></tr>" + bn_rows + "</table>" if bn_rows else ""}

{"<h2>4. Load Zones</h2><table><tr><th>Zone</th><th>Period</th><th>Duration</th></tr>" + zone_rows + "</table>" if zone_rows else ""}

{"<h2>5. Anomalies</h2><table><tr><th>Time</th><th>Event</th></tr>" + anom_rows + "</table>" if anom_rows else ""}

{top5_html(top5_cpu, 'CPU')}
{top5_html(top5_ram, 'RAM')}
{top5_html(top5_gpu, 'GPU')}

<h2>6. Event Log</h2>
<p style="font-size:.7rem;opacity:.4">{warn_count} warnings / {danger_count} dangers / {idle_count} idle events</p>
<table><tr><th>Time</th><th></th><th>Message</th></tr>
{event_rows if event_rows else '<tr><td colspan="3" style="text-align:center;opacity:.3">No events</td></tr>'}
</table>

</body></html>'''

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path
