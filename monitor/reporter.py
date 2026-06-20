"""Detailed session report — NDJSON -> HTML with event-cause analysis."""
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
    if not rows:
        return None

    cpu_vals = [r['cpu'] for r in rows]
    gpu_vals = [r['gpu'] for r in rows]
    gt_vals = [r['gt'] for r in rows]
    ram_vals = [r['ram'] for r in rows]

    cpu_avg, cpu_max = stat.mean(cpu_vals), max(cpu_vals)
    gpu_avg, gpu_max = stat.mean(gpu_vals), max(gpu_vals)
    gt_avg, gt_max = stat.mean(gt_vals), max(gt_vals)
    ram_avg = stat.mean(ram_vals)

    cpu_st = _threshold(cpu_avg, 70, 90)
    gpu_st = _threshold(gpu_avg, 80, 95)
    gt_st = _threshold(gt_max, 75, 85)
    ram_st = _threshold(ram_avg, 70, 90)

    def st_html(label, st, lines):
        icons = {'good': '✅', 'warning': '⚠️', 'danger': '🔥'}
        ico = icons.get(st, 'ℹ️')
        l = ''.join(f'<tr><td>{x}</td></tr>' for x in lines)
        return f'<div class="comp {st}"><div class="comp-h">{ico} {label}</div><table class="comp-d">{l}</table></div>'

    # Bottleneck frequency analysis from NDJSON rows
    gpu_bn = 0
    cpu_bn = 0
    gpu_bn_streaks = []  # track consecutive bottleneck lengths
    cpu_bn_streaks = []
    streak = 0
    streak_type = None
    for r in rows:
        if r['gpu'] > 90 and r['cpu'] < 60:
            gpu_bn += 1
            if streak_type == 'gpu': streak += 1
            else:
                if streak_type == 'cpu' and streak > 0: cpu_bn_streaks.append(streak)
                streak = 1
                streak_type = 'gpu'
        elif r['cpu'] > 85 and r['gpu'] < 70:
            cpu_bn += 1
            if streak_type == 'cpu': streak += 1
            else:
                if streak_type == 'gpu' and streak > 0: gpu_bn_streaks.append(streak)
                streak = 1
                streak_type = 'cpu'
        else:
            if streak_type == 'gpu' and streak > 0: gpu_bn_streaks.append(streak)
            if streak_type == 'cpu' and streak > 0: cpu_bn_streaks.append(streak)
            streak = 0
            streak_type = None
    if streak_type == 'gpu' and streak > 0: gpu_bn_streaks.append(streak)
    if streak_type == 'cpu' and streak > 0: cpu_bn_streaks.append(streak)

    total = len(rows)
    cpu_lines = [f'평균: {_fmt(cpu_avg)}% | 최고: {_fmt(cpu_max)}%']
    if cpu_max > 90: cpu_lines.append(f'⚠️ CPU 최대 {_fmt(cpu_max)}% — 부하 매우 높음')
    else: cpu_lines.append(f'CPU 부하 범위: {_fmt(min(cpu_vals))}% ~ {_fmt(cpu_max)}%')
    if cpu_bn > 0 and total > 0:
        cpu_bn_pct = cpu_bn / total * 100
        avg_cpu_dur = stat.mean(cpu_bn_streaks) * (rows[1]['t'] - rows[0]['t']) if cpu_bn_streaks else 0
        cpu_lines.append(f'⚙️ CPU 병목 {cpu_bn}회 ({cpu_bn_pct:.0f}%) · 평균 지속 {avg_cpu_dur:.0f}초')
    else:
        cpu_lines.append(f'🟢 CPU 병목 없음')

    gpu_lines = [f'평균: {_fmt(gpu_avg)}% | 최고: {_fmt(gpu_max)}%']
    gpu_lines.append(f'온도: 평균 {_fmt(gt_avg)}°C | 최고 {_fmt(gt_max)}°C')
    if gt_max > 85: gpu_lines.append(f'🔥 GPU 온도 {_fmt(gt_max)}°C — 위험!')
    elif gt_max > 75: gpu_lines.append(f'⚠️ GPU 최고 온도 {_fmt(gt_max)}°C')
    else: gpu_lines.append(f'🟢 GPU 온도 안정적 (최고 {_fmt(gt_max)}°C)')
    if gpu_max > 90: gpu_lines.append(f'⚠️ GPU 거의 풀가동 ({_fmt(gpu_max)}%)')
    if gpu_bn > 0 and total > 0:
        gpu_bn_pct = gpu_bn / total * 100
        avg_gpu_dur = stat.mean(gpu_bn_streaks) * (rows[1]['t'] - rows[0]['t']) if gpu_bn_streaks else 0
        max_gpu_streak = max(gpu_bn_streaks) * (rows[1]['t'] - rows[0]['t']) if gpu_bn_streaks else 0
        gpu_lines.append(f'🎮 GPU 병목 {gpu_bn}회 ({gpu_bn_pct:.0f}%) · 평균 {avg_gpu_dur:.0f}초 · 최장 {max_gpu_streak:.0f}초')
    else:
        gpu_lines.append(f'🟢 GPU 병목 없음')

    ram_lines = [f'평균: {_fmt(ram_avg)}%']
    if ram_avg > 85: ram_lines.append('⚠️ 메모리 부족')
    elif ram_avg < 50: ram_lines.append('🟢 메모리 여유')
    else: ram_lines.append('🟡 메모리 적정')

    # Event log: success/info excluded, show detail
    filtered = [e for e in logs if e['type'] in ('warning', 'danger', 'idle')]
    wc = sum(1 for e in filtered if e['type'] == 'warning')
    dc = sum(1 for e in filtered if e['type'] == 'danger')
    ic = sum(1 for e in filtered if e['type'] == 'idle')

    event_rows = ''
    for e in filtered[-30:]:
        cls = 'l-w' if e['type'] == 'warning' else 'l-d' if e['type'] == 'danger' else 'l-i'
        # detail message (cause analysis)
        dt = e.get('detail', '') or ''
        detail_html = ''
        if dt:
            detail_html = '<div class="evt-detail">' + dt.replace('\n', '<br>') + '</div>'
        event_rows += f'<tr class="{cls}">'
        event_rows += f'<td class="evt-t">{e["time"]}</td>'
        event_rows += f'<td class="evt-i">{e["icon"]}</td>'
        event_rows += f'<td class="evt-m">{e["msg"]}{detail_html}</td>'
        event_rows += '</tr>\n'

    # Anomalies (keep this)
    anom_rows = ''
    for i in range(1, len(rows)):
        p, c = rows[i-1], rows[i]
        anoms = []
        if c['cpu'] - p['cpu'] > 30:
            anoms.append(f'CPU {p["cpu"]:.0f}% → {c["cpu"]:.0f}% (+{c["cpu"]-p["cpu"]:.0f}p 급등)')
        if c['gt'] - p['gt'] > 5:
            anoms.append(f'온도 {p["gt"]:.0f}°C → {c["gt"]:.0f}°C (+{c["gt"]-p["gt"]:.0f}°C 상승)')
        if p['gpu'] > 80 and c['gpu'] < 20:
            anoms.append(f'GPU {p["gpu"]:.0f}% → {c["gpu"]:.0f}% (게임 종료 추정)')
        if anoms:
            t_str = datetime.fromtimestamp(start_time + c['t']).strftime('%H:%M:%S') if start_time else f'{c["t"]:.0f}s'
            for a in anoms:
                anom_rows += f'<tr><td>{t_str}</td><td>{a}</td></tr>\n'

    def top5_html(items, label):
        if not items:
            return ''
        h = f'<h2>Top 5 {label}</h2><table><tr><th>#</th><th>프로세스</th><th>점유율</th></tr>'
        for i, (n, v) in enumerate(items, 1):
            cls = ' class="warn"' if v > 50 else ''
            h += f'<tr{cls}><td>{i}</td><td>{n}</td><td>{v}%</td></tr>'
        h += f'<tr style="opacity:.4"><td></td><td>합계</td><td>{sum(v for _,v in items):.1f}%</td></tr></table>'
        return h

    # Labels en minutes, largeur proportionnelle
    chart_w = max(400, len(rows) * 4)  # 4px par point de donnees
    c_labels = json.dumps([f'{int(r["t"]/60)}m' for r in rows], ensure_ascii=False)
    c_cpu = json.dumps([r['cpu'] for r in rows])
    c_gpu = json.dumps([r['gpu'] for r in rows])
    c_gt = json.dumps([r['gt'] for r in rows])

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>PC Monitor - 상세 리포트</title>
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
.chart-wr{{height:200px;margin:12px 0;overflow-x:auto;width:100%}}
.chart-inner{{width:{chart_w}px;height:200px}}
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
.evt-t{{white-space:nowrap;width:55px;font-size:.65rem;opacity:.4;vertical-align:top;padding-top:6px}}
.evt-i{{width:22px;font-size:.85rem;padding-top:6px}}
.evt-m{{font-size:.78rem}}
.evt-detail{{margin-top:4px;padding:6px 8px;border-radius:4px;background:rgba(255,255,255,.02);font-size:.7rem;line-height:1.5;opacity:.7;white-space:pre-wrap}}
.l-d .evt-detail{{background:rgba(239,68,68,.04)}}
.l-w .evt-detail{{background:rgba(245,158,11,.04)}}
.l-i .evt-detail{{background:rgba(168,130,255,.04)}}
</style></head>
<body>
<h1>PC Monitor - 상세 리포트</h1>
<p class="sub">{duration}</p>

<h2>1. 구성요소 상태</h2>
{st_html('CPU', cpu_st, cpu_lines)}
{st_html('GPU', gpu_st, gpu_lines)}
{st_html('RAM', ram_st, ram_lines)}

<h2>2. 타임라인 차트</h2>
<div class="chart-wr"><div class="chart-inner"><canvas id="chart"></canvas></div></div>
<script>
new Chart(document.getElementById('chart'), {{
  type:'line', data:{{
    labels:{c_labels},
    datasets:[
      {{label:'CPU',data:{c_cpu},borderColor:'#00d4ff',borderWidth:1.5,fill:false,tension:.3,pointRadius:0,yAxisID:'y'}},
      {{label:'GPU',data:{c_gpu},borderColor:'#ff6b35',borderWidth:1.5,fill:false,tension:.3,pointRadius:0,yAxisID:'y'}},
      {{label:'온도',data:{c_gt},borderColor:'#ef4444',borderWidth:1,borderDash:[3,3],fill:false,tension:.3,pointRadius:0,yAxisID:'y1'}},
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

{"<h2>3. 이상치</h2><table><tr><th>시간</th><th>내용</th></tr>" + anom_rows + "</table>" if anom_rows else ""}

{top5_html(top5_cpu, 'CPU')}
{top5_html(top5_ram, 'RAM')}
{top5_html(top5_gpu, 'GPU')}

<h2>4. 이벤트 로그</h2>
<p style="font-size:.7rem;opacity:.4">⚠️ 경고 {wc}회 / 🔥 위험 {dc}회 / 💤 유휴 {ic}회</p>
<table><tr><th style="width:55px">시간</th><th style="width:22px"></th><th>내용</th></tr>
{event_rows if event_rows else '<tr><td colspan="3" style="text-align:center;opacity:.3">비정상 이벤트 없음</td></tr>'}
</table>

</body></html>'''

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path
