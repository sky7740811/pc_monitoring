import psutil


def get_top_processes(n=8):
    processes = []
    skip = {'System Idle Process', 'System', 'Registry', 'smss.exe',
            'Secure System', 'Memory Compression'}
    cores = psutil.cpu_count() or 1
    try:
        iter_proc = psutil.process_iter(['name', 'pid', 'cpu_percent', 'memory_info'])
        for proc in iter_proc:
            try:
                info = proc.info
                if info['name'] in skip: continue
                if info['name'] and info['cpu_percent'] is not None:
                    mem_mb = (info['memory_info'].rss / (1024 * 1024)
                              if info['memory_info'] else 0)
                    processes.append({
                        'name': info['name'],
                        'pid': info['pid'],
                        'cpu_percent': round(info['cpu_percent'] / cores, 1),
                        'memory_mb': round(mem_mb, 1),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        return []

    processes.sort(key=lambda p: p['cpu_percent'], reverse=True)
    return processes[:n]
