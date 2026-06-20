import subprocess


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
