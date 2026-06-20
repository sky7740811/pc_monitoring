import psutil


def get_memory_info():
    mem = psutil.virtual_memory()
    total_gb = mem.total / (1024 ** 3)
    used_gb = mem.used / (1024 ** 3)
    return {
        'percent': round(mem.percent, 1),
        'used_gb': round(used_gb, 1),
        'total_gb': round(total_gb, 1),
    }
