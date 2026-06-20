import json
import logging
import os
import time
from datetime import datetime

import psutil

from monitor.cpu import get_cpu_info
from monitor.gpu import get_gpu_info
from monitor.memory import get_memory_info
from monitor.disk import get_disk_speed
from monitor.network import get_network_speed
from monitor.processes import get_top_processes
from monitor.diagnostic import analyze
from monitor.events import check as check_events, check_idle
from monitor.gpu import get_gpu_processes

logger = logging.getLogger('pc-monitor')


class SystemCollector:
    def __init__(self):
        self.prev_time = None
        self.history = []
        self.log_buffer = []
        self.start_time = None
        self._proc_cache = []
        self._slow_tick = 0
        self._proc_history = {}  # {name: {cpu: [], ram: [], gpu: []}}
        self._gpu_context = set()  # process names with GPU context
        self.total_ram_mb = 0
        self._ndjson_path = None
        self._ndjson_file = None
        self._prev_proc_cpu: dict[int, float] = {}  # {pid: cpu_percent}
        self.stats = {
            'cpu_pct': [], 'gpu_pct': [], 'gpu_temp': [],
            'cpu_temp': [], 'vram_pct': [], 'mem_pct': [],
        }

    def prime(self):
        from monitor import cpu, disk, network
        cpu.prime()
        disk.prime()
        network.prime()
        psutil.cpu_percent(interval=None, percpu=True)
        self.prev_time = time.time()
        self.start_time = time.time()
        self.total_ram_mb = round(psutil.virtual_memory().total / (1024 * 1024), 0)
        self._log_event('info', '🚀', '세션 시작', 'PC Monitor monitoring session started.')
        # Open NDJSON raw log
        try:
            raw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'log', 'raw')
            os.makedirs(raw_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            self._ndjson_path = os.path.join(raw_dir, f'{ts}.ndjson')
            self._ndjson_file = open(self._ndjson_path, 'w', encoding='utf-8')
        except Exception as e:
            logger.warning(f'NDJSON init failed: {e}')
        # Prime process CPU + populate cache
        try:
            self._proc_cache = get_top_processes(n=8)
        except Exception:
            pass

    def _log_event(self, etype, icon, msg, detail=''):
        now = datetime.now().strftime('%H:%M:%S')
        entry = {'time': now, 'type': etype, 'icon': icon, 'msg': msg, 'detail': detail}
        self.log_buffer.append(entry)
        if len(self.log_buffer) > 500:
            self.log_buffer.pop(0)

    def _update_stats(self, data):
        cpu = data['cpu']
        gpu = data['gpu']
        mem = data['memory']
        self.stats['cpu_pct'].append(cpu['percent'])
        self.stats['gpu_pct'].append(gpu['percent'])
        self.stats['gpu_temp'].append(gpu.get('temp', 0))
        if cpu.get('temp') is not None:
            self.stats['cpu_temp'].append(cpu['temp'])
        self.stats['vram_pct'].append(gpu.get('vram_percent', 0))
        self.stats['mem_pct'].append(mem['percent'])

    def _avg(self, arr):
        return round(sum(arr) / len(arr), 1) if arr else 0

    def _max(self, arr):
        return round(max(arr), 1) if arr else 0

    def _min(self, arr):
        return round(min(arr), 1) if arr else 0

    def get_summary(self):
        s = self.stats
        dur = time.time() - self.start_time if self.start_time else 0
        h, rem = divmod(int(dur), 3600)
        m, sec = divmod(rem, 60)
        return {
            'duration': f'{h}h {m}m {sec}s' if h else f'{m}m {sec}s',
            'cpu_avg': self._avg(s['cpu_pct']),
            'cpu_max': self._max(s['cpu_pct']),
            'gpu_avg': self._avg(s['gpu_pct']),
            'gpu_max': self._max(s['gpu_pct']),
            'gpu_temp_avg': self._avg(s['gpu_temp']),
            'gpu_temp_max': self._max(s['gpu_temp']),
            'cpu_temp_avg': self._avg(s['cpu_temp']),
            'cpu_temp_max': self._max(s['cpu_temp']),
            'vram_max': self._max(s['vram_pct']),
            'mem_avg': self._avg(s['mem_pct']),
            'warnings': sum(1 for e in self.log_buffer if e['type'] == 'warning'),
            'dangers': sum(1 for e in self.log_buffer if e['type'] == 'danger'),
        }

    def get_process_top5(self, metric='cpu'):
        """Retourne top 5 processus par part de consommation (% du total).
        La somme des parts (top5 + others) = 100%."""
        names = {}
        for name, h in self._proc_history.items():
            if metric == 'gpu' and name not in self._gpu_context:
                continue
            vals = [v for v in h[metric] if v > 0]
            if vals:
                names[name] = sum(vals)
            else:
                names[name] = 0
        total = sum(names.values())
        if total == 0:
            return []
        # Convertir en % et trier
        shares = [(n, round(v / total * 100, 1)) for n, v in names.items() if v > 0]
        shares.sort(key=lambda x: x[1], reverse=True)
        top = shares[:5]
        # Ajouter "Others" (arrondir pour que total = 100.0)
        other_sum = 100.0 - sum(s[1] for s in shares[:5])
        if other_sum > 0.05:
            top.append(('Others', round(other_sum, 1)))
        return top

    def save_html(self):
        summary = self.get_summary()
        start_dt = datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'log')
        os.makedirs(log_dir, exist_ok=True)
        fname = datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d_%H%M%S') + '.html'
        fpath = os.path.join(log_dir, fname)

        # Filter out "normal" events for the log
        log_events_filtered = [e for e in self.log_buffer if e['type'] != 'success']
        rows = ''
        for e in log_events_filtered:
            rows += f'<tr><td>{e["time"]}</td><td>{e["icon"]}</td><td>{e["type"]}</td><td>{e["msg"]}</td></tr>\n'
        event_count = len(log_events_filtered)
        if not rows:
            rows = '<tr><td colspan="4" style="text-align:center;opacity:.3">Aucun evenement anormal</td></tr>'

        s = summary
        top5_cpu = self.get_process_top5('cpu')
        top5_ram = self.get_process_top5('ram')
        top5_gpu = self.get_process_top5('gpu')

        # Human diagnostic
        diag_lines = []
        if s['cpu_max'] > 90:
            diag_lines.append(f'CPU가 최대 {s["cpu_max"]}%까지 올라갔습니다. 게임 중 CPU 부하가 높았습니다.')
        elif s['cpu_avg'] < 30:
            diag_lines.append(f'CPU는 평균 {s["cpu_avg"]}%로 여유롭게 동작했습니다.')
        else:
            diag_lines.append(f'CPU는 평균 {s["cpu_avg"]}%로 동작했습니다.')

        if s['gpu_max'] > 95:
            diag_lines.append(f'GPU가 최대 {s["gpu_max"]}%까지 사용되어 거의 풀가동 상태였습니다.')
        elif s['gpu_avg'] > 70:
            diag_lines.append(f'GPU를 평균 {s["gpu_avg"]}% 활용했습니다.')
        else:
            diag_lines.append(f'GPU는 평균 {s["gpu_avg"]}% 사용되었습니다.')

        if s['gpu_temp_max'] > 85:
            diag_lines.append(f'GPU 온도가 최대 {s["gpu_temp_max"]}°C까지 올라갔습니다. 온도 관리가 필요합니다.')
        elif s['gpu_temp_max'] > 75:
            diag_lines.append(f'GPU 최고 온도는 {s["gpu_temp_max"]}°C입니다.')
        else:
            diag_lines.append(f'GPU 온도는 최대 {s["gpu_temp_max"]}°C로 안정적이었습니다.')

        if s['mem_avg'] > 85:
            diag_lines.append(f'RAM 사용률 평균 {s["mem_avg"]}%로 메모리가 부족했습니다.')
        elif s['mem_avg'] > 70:
            diag_lines.append(f'RAM 평균 {s["mem_avg"]}% 사용.')
        else:
            diag_lines.append(f'RAM은 평균 {s["mem_avg"]}% 사용으로 충분했습니다.')

        if s['warnings'] > 0 or s['dangers'] > 0:
            diag_lines.append(f'경고 {s["warnings"]}회, 위험 {s["dangers"]}회 발생했습니다.')
        else:
            diag_lines.append('안정적으로 동작했습니다.')

        diag_html = '<br>'.join(diag_lines)

        # Top5 tables (toutes les valeurs sont déjà en %)
        def top5_table(items, high_thresh=50, force=False):
            if not items:
                return ''
            if not force and items[0][1] == 0:
                return ''
            rows_t5 = ''
            for i, (n, v) in enumerate(items, 1):
                high = ' style="color:#ef4444"' if v > high_thresh else ''
                rows_t5 += f'<tr><td>{i}</td><td>{n}</td><td{high}>{v}%</td></tr>'
            # Total row
            total_pct = sum(v for _, v in items)
            rows_t5 += f'<tr style="opacity:.4"><td></td><td>Total</td><td>{round(total_pct,1)}%</td></tr>'
            return f'''<table class="summary">
<tr><th>#</th><th>Process</th><th>Share</th></tr>
{rows_t5}</table>'''

        def top5_section(label, items, thresh=50, force=False):
            tbl = top5_table(items, thresh, force)
            if not tbl:
                return ''
            return f'<h2>Top 5 {label}</h2>{tbl}'

        html = f'''<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>PC Monitor - {start_dt}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',sans-serif;background:#080c14;color:#d0d5df;padding:24px;max-width:960px;margin:0 auto}}
h1{{font-size:1.2rem;color:#e8ecf4;margin-bottom:4px}}
.sub{{opacity:.4;font-size:.8rem;margin-bottom:20px}}
h2{{font-size:.9rem;color:#8892a0;margin:16px 0 8px;letter-spacing:.5px}}
table{{width:100%;border-collapse:collapse;font-size:.8rem}}
th,td{{padding:6px 10px;text-align:left;border-bottom:1px solid rgba(255,255,255,.04)}}
th{{color:#8892a0;font-weight:600;font-size:.7rem;letter-spacing:.5px}}
.summary td:first-child{{opacity:.5}}
.summary td:nth-child(2){{font-weight:600;color:#e8ecf4}}
.danger{{color:#ef4444}} .warning{{color:#f59e0b}} .success{{color:#10b981}} .info{{color:#60a5fa}}
.diag-box{{background:rgba(16,185,129,.05);border:1px solid rgba(16,185,129,.15);border-radius:8px;padding:12px 14px;margin:12px 0;font-size:.8rem;line-height:1.6;color:#b0b8c4}}
.diag-box.danger{{background:rgba(239,68,68,.06);border-color:rgba(239,68,68,.2)}}
.warn{{color:#ef4444;font-weight:600}}
</style></head>
<body>
<h1>PC Monitor Session Report</h1>
<p class="sub">{start_dt} ~ {s["duration"]}</p>

<div class="diag-box{' danger' if s['dangers'] > 0 else ''}">{diag_html}</div>

<h2>Summary</h2>
<table class="summary">
<tr><td>Duration</td><td>{s["duration"]}</td></tr>
<tr><td>CPU</td><td>avg {s["cpu_avg"]}% / max {s["cpu_max"]}%</td></tr>
<tr><td>GPU</td><td>avg {s["gpu_avg"]}% / max {s["gpu_max"]}%</td></tr>
<tr><td>GPU Temp</td><td>avg {s["gpu_temp_avg"]}°C / max {s["gpu_temp_max"]}°C</td></tr>
<tr><td>RAM avg</td><td>{s["mem_avg"]}%</td></tr>
<tr><td>Alerts</td><td>⚠️ {s["warnings"]} / 🔥 {s["dangers"]}</td></tr>
</table>

{top5_section('CPU', top5_cpu, 50)}
{top5_section('RAM', top5_ram, 50)}
{top5_section('GPU', top5_gpu, 50, True)}

<h2>Event Log ({event_count} entries)</h2>
<table>
<tr><th>Time</th><th></th><th>Type</th><th>Message</th></tr>
{rows}
</table>
</body></html>'''

        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f'Session saved: {fpath}')
        return fpath

    def generate_report(self):
        """Generate detailed HTML report from NDJSON + close log."""
        if self._ndjson_file:
            try:
                self._ndjson_file.close()
            except Exception:
                pass
        try:
            from monitor.reporter import generate
            s = self.get_summary()
            top5_cpu = self.get_process_top5('cpu')
            top5_ram = self.get_process_top5('ram')
            top5_gpu = self.get_process_top5('gpu')
            path = generate(self._ndjson_path, self.start_time, s['duration'],
                          s, self.log_buffer, top5_cpu, top5_ram, top5_gpu)
            if path:
                logger.info(f'Detailed report saved: {path}')
            return path
        except Exception as e:
            logger.error(f'Report generation failed: {e}')
            return None

    def collect(self):
        now = time.time()
        dt = now - self.prev_time if self.prev_time else 1.0

        try:
            cpu = get_cpu_info()
        except Exception as e:
            logger.warning(f'CPU error: {e}')
            cpu = {'percent': 0, 'per_core': [], 'cores': 0, 'freq': None}

        try:
            gpu = get_gpu_info()
        except Exception as e:
            logger.warning(f'GPU error: {e}')
            gpu = {'name': 'N/A', 'percent': 0, 'temp': 0,
                   'vram_used': 0, 'vram_total': 0, 'vram_percent': 0, 'clock': 0}

        try:
            memory = get_memory_info()
        except Exception as e:
            logger.warning(f'Memory error: {e}')
            memory = {'percent': 0, 'used_gb': 0, 'total_gb': 0}

        try:
            disk = get_disk_speed(dt)
        except Exception as e:
            logger.warning(f'Disk error: {e}')
            disk = {'read_speed': 0, 'write_speed': 0}

        try:
            network = get_network_speed(dt)
        except Exception as e:
            logger.warning(f'Network error: {e}')
            network = {'download_speed': 0, 'upload_speed': 0}

        self._slow_tick += 1
        if self._slow_tick % 4 == 1:
            try:
                self._proc_cache = get_top_processes()
            except Exception as e:
                logger.warning(f'Process error: {e}')
                self._proc_cache = []
            # Merge GPU usage into process list (match by PID)
            try:
                gpu_procs = get_gpu_processes()
                gpu_map = {p['pid']: p for p in gpu_procs}
                for p in self._proc_cache:
                    g = gpu_map.get(p.get('pid'))
                    if g:
                        p['gpu_sm'] = g['gpu_sm']
                        p['gpu_mem'] = g['gpu_mem']
                # Add GPU-only processes not already in the list
                existing = {p.get('pid') for p in self._proc_cache}
                for gp in gpu_procs:
                    if gp['pid'] not in existing:
                        self._proc_cache.append({
                            'name': gp['name'],
                            'pid': gp['pid'],
                            'cpu_percent': 0,
                            'memory_mb': 0,
                            'gpu_sm': gp['gpu_sm'],
                            'gpu_mem': gp['gpu_mem'],
                        })
                # Track GPU context for report
                for gp in gpu_procs:
                    self._gpu_context.add(gp['name'])
                # Cap total at 10 (CPU + GPU combined)
                self._proc_cache.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
                self._proc_cache = self._proc_cache[:8]
            except Exception:
                pass
        processes = self._proc_cache

        # Track per-process history for session top5
        for p in processes:
            name = p['name']
            if name not in self._proc_history:
                self._proc_history[name] = {'cpu': [], 'ram': [], 'gpu': []}
            h = self._proc_history[name]
            h['cpu'].append(p.get('cpu_percent', 0))
            h['ram'].append(p.get('memory_mb', 0))
            h['gpu'].append(p.get('gpu_sm', 0))
            # Keep last 300 samples (~5 min at 1s, ~10 min at 2s)
            for k in ('cpu', 'ram', 'gpu'):
                if len(h[k]) > 300:
                    h[k].pop(0)

        self.prev_time = now

        # CPU spike detection: track which process spiked most
        cpu_spike = None
        for p in processes:
            pid = p.get('pid')
            cpu_now = p.get('cpu_percent', 0)
            if pid and pid in self._prev_proc_cpu:
                delta = cpu_now - self._prev_proc_cpu[pid]
                if delta > 5 and (cpu_spike is None or delta > cpu_spike['delta']):
                    cpu_spike = {'name': p['name'], 'display_name': p.get('display_name', p['name']),
                                 'pid': pid, 'delta': round(delta, 1), 'current': cpu_now}
            self._prev_proc_cpu[pid] = cpu_now

        data = {
            'cpu': cpu,
            'cpu_spike': cpu_spike,
            'gpu': gpu,
            'memory': memory,
            'disk': disk,
            'network': network,
            'processes': processes,
        }

        self.history.append(data)
        if len(self.history) > 60:
            self.history.pop(0)

        try:
            data['diagnostic'] = analyze(data, self.history)
        except Exception as e:
            logger.warning(f'Diagnostic error: {e}')
            data['diagnostic'] = {
                'health_score': 0, 'bottleneck': None,
                'alerts': [{'type': 'danger', 'icon': '⚠️', 'title': '진단 오류',
                            'message': '시스템 분석 중 오류가 발생했습니다'}],
            }

        # Events logging
        log_ok = False
        try:
            events = check_events(data, self.history)
            idle = check_idle(processes)
            all_events = events + idle
            for ev in all_events:
                self._log_event(ev['type'], ev['icon'], ev['msg'], ev.get('detail', ''))
            data['log_events'] = all_events
            log_ok = True
        except Exception as e:
            logger.warning(f'Events error: {e}')
            data['log_events'] = []
        try:
            data['log_buffer'] = self.log_buffer[-50:]
        except Exception:
            data['log_buffer'] = []
        try:
            data['log_summary'] = self.get_summary()
        except Exception:
            data['log_summary'] = {}

        # Update session stats
        try:
            self._update_stats(data)
        except Exception:
            pass

        # High-resource processes (for kill buttons, exclude system)
        try:
            from monitor.events import SYSTEM_PROCS
            high = [p for p in data.get('processes', [])
                    if p['name'] not in SYSTEM_PROCS
                    and (p.get('cpu_percent', 0) > 10 or p.get('memory_mb', 0) > 500)]
            data['high_procs'] = high
        except Exception:
            data['high_procs'] = []

        # NDJSON raw log
        if self._ndjson_file and not self._ndjson_file.closed:
            try:
                t = round(time.time() - self.start_time, 1) if self.start_time else 0
                gpu_info = data.get('gpu', {})
                row = {
                    't': t, 'cpu': data['cpu']['percent'],
                    'gpu': gpu_info.get('percent', 0), 'gt': gpu_info.get('temp', 0),
                    'ram': data['memory']['percent'], 'vp': gpu_info.get('vram_percent', 0),
                    'alerts': len(data.get('log_events', [])),
                }
                line = json.dumps(row, ensure_ascii=False) + '\n'
                self._ndjson_file.write(line)
                self._ndjson_file.flush()
            except Exception as e:
                logger.warning(f'NDJSON write: {e}')

        return data
