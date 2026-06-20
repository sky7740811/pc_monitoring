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

            name = parts[0]
            gpu_percent = int(parts[1])
            gpu_temp = int(parts[2])
            vram_used = int(parts[3])
            vram_total = int(parts[4])
            clock = int(parts[5])

            return {
                'name': name,
                'percent': gpu_percent,
                'temp': gpu_temp,
                'vram_used': vram_used,
                'vram_total': vram_total,
                'vram_percent': round((vram_used / vram_total * 100) if vram_total > 0 else 0, 1),
                'clock': clock,
            }
    except Exception:
        pass

    return {
        'name': 'N/A', 'percent': 0, 'temp': 0,
        'vram_used': 0, 'vram_total': 0, 'vram_percent': 0, 'clock': 0,
    }


_gpu_proc_cache = []
_gpu_proc_time = 0


def get_gpu_processes():
    """Return list of {name, sm, mem} for processes using GPU."""
    global _gpu_proc_cache, _gpu_proc_time
    now = time.time()
    if now - _gpu_proc_time < 3:
        return _gpu_proc_cache
    _gpu_proc_time = now

    try:
        result = subprocess.run(
            ['nvidia-smi', 'pmon', '-s', 'u', '-c', '1'],
            capture_output=True, text=True, timeout=5,
        )
        procs = {}
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            try:
                pid = int(parts[1])
                sm = parts[3]
                mem = parts[4]
                name = parts[8]
                if name == 'command':
                    continue
                sm_val = int(sm) if sm != '-' else 0
                mem_val = int(mem) if mem != '-' else 0
                if name != '-' and (sm_val > 0 or mem_val > 0):
                    procs[name] = {'name': name, 'gpu_sm': sm_val, 'gpu_mem': mem_val}
            except (ValueError, IndexError):
                continue
        _gpu_proc_cache = list(procs.values())
        return _gpu_proc_cache
    except Exception:
        return []
