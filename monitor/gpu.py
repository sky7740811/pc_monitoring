import os
import subprocess
import time


def get_gpu_info():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,utilization.gpu,temperature.gpu,'
                           'memory.used,memory.total,clocks.current.graphics',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            line = result.stdout.strip().split('\n')[0]
            parts = [p.strip() for p in line.split(',')]
            return {
                'name': parts[0],
                'percent': int(parts[1]),
                'temp': int(parts[2]),
                'vram_used': int(parts[3]),
                'vram_total': int(parts[4]),
                'vram_percent': round(int(parts[3]) / int(parts[4]) * 100 if int(parts[4]) > 0 else 0, 1),
                'clock': int(parts[5]),
            }
    except Exception:
        pass
    return {'name': 'N/A', 'percent': 0, 'temp': 0, 'vram_used': 0, 'vram_total': 0, 'vram_percent': 0, 'clock': 0}


_gpu_proc_cache = []
_gpu_proc_time = 0


def get_gpu_processes():
    """Return list of {pid, name, gpu_sm, gpu_mem} for processes using GPU."""
    global _gpu_proc_cache, _gpu_proc_time
    now = time.time()
    if now - _gpu_proc_time < 3:
        return _gpu_proc_cache
    _gpu_proc_time = now

    procs = {}

    # Method 1: nvidia-smi pmon (SM/mem utilization)
    try:
        result = subprocess.run(
            ['nvidia-smi', 'pmon', '-s', 'u', '-c', '1'],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 10:
                continue
            try:
                pid = int(parts[1])
                sm = parts[3]; mem = parts[4]
                sm_val = int(sm) if sm != '-' else 0
                mem_val = int(mem) if mem != '-' else 0
                name = ' '.join(parts[9:]).strip() if len(parts) > 10 else parts[9]
                if name in ('command', '-'):
                    continue
                if sm_val > 0 or mem_val > 0:
                    procs[pid] = {'pid': pid, 'name': name, 'gpu_sm': sm_val, 'gpu_mem': mem_val}
            except (ValueError, IndexError):
                continue
    except Exception:
        pass

    # Method 2: nvidia-smi query-compute-apps (all GPU-context processes)
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid,process_name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=3,
        )
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('['):
                continue
            parts = line.split(', ', 1)
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
                if pid not in procs:
                    name = os.path.basename(parts[1]) if parts[1] != '[N/A]' else ''
                    if name:
                        procs[pid] = {'pid': pid, 'name': name, 'gpu_sm': 0, 'gpu_mem': 0}
            except ValueError:
                continue
    except Exception:
        pass

    _gpu_proc_cache = list(procs.values())
    return _gpu_proc_cache
