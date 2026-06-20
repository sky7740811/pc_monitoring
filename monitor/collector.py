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
        self._log_event('info', '🚀', '세션 시작')
        # Prime process CPU + populate cache
        try:
            self._proc_cache = get_top_processes(n=8)
        except Exception:
            pass

    def _log_event(self, etype, icon, msg):
        now = datetime.now().strftime('%H:%M:%S')
        entry = {'time': now, 'type': etype, 'icon': icon, 'msg': msg}
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

    def save_html(self):
        summary = self.get_summary()
        start_dt = datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'log')
        os.makedirs(log_dir, exist_ok=True)
        fname = datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d_%H%M%S') + '.html'
        fpath = os.path.join(log_dir, fname)

        rows = ''
        for e in self.log_buffer:
            rows += f'<tr><td>{e["time"]}</td><td>{e["icon"]}</td><td>{e["type"]}</td><td>{e["msg"]}</td></tr>\n'

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
</style></head>
<body>
<h1>PC Monitor Session Report</h1>
<p class="sub">{start_dt} ~ {summary["duration"]}</p>

<h2>Summary</h2>
<table class="summary">
<tr><td>Duration</td><td>{summary["duration"]}</td></tr>
<tr><td>CPU</td><td>avg {summary["cpu_avg"]}% / max {summary["cpu_max"]}%</td></tr>
<tr><td>GPU</td><td>avg {summary["gpu_avg"]}% / max {summary["gpu_max"]}%</td></tr>
<tr><td>GPU Temp</td><td>avg {summary["gpu_temp_avg"]}°C / max {summary["gpu_temp_max"]}°C</td></tr>
<tr><td>CPU Temp</td><td>avg {summary["cpu_temp_avg"]}°C / max {summary["cpu_temp_max"]}°C</td></tr>
<tr><td>VRAM Max</td><td>{summary["vram_max"]}%</td></tr>
<tr><td>RAM avg</td><td>{summary["mem_avg"]}%</td></tr>
<tr><td>Alerts</td><td>⚠️ {summary["warnings"]} / 🔥 {summary["dangers"]}</td></tr>
</table>

<h2>Event Log ({len(self.log_buffer)} entries)</h2>
<table>
<tr><th>Time</th><th></th><th>Type</th><th>Message</th></tr>
{rows}
</table>
</body></html>'''

        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f'Session saved: {fpath}')
        return fpath

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
                # Cap total at 10 (CPU + GPU combined)
                self._proc_cache.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)
                self._proc_cache = self._proc_cache[:10]
            except Exception:
                pass
        processes = self._proc_cache

        self.prev_time = now

        data = {
            'cpu': cpu,
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
                self._log_event(ev['type'], ev['icon'], ev['msg'])
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

        return data
