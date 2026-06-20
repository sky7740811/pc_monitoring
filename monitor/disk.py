import psutil


_prev = None


def prime():
    global _prev
    _prev = psutil.disk_io_counters()


def get_disk_speed(dt=1.0):
    global _prev
    curr = psutil.disk_io_counters()
    if _prev is None:
        _prev = curr
        return {'read_speed': 0.0, 'write_speed': 0.0}
    read_bps = max(0, curr.read_bytes - _prev.read_bytes) / max(dt, 0.1)
    write_bps = max(0, curr.write_bytes - _prev.write_bytes) / max(dt, 0.1)
    _prev = curr
    return {
        'read_speed': round(read_bps / (1024 * 1024), 1),
        'write_speed': round(write_bps / (1024 * 1024), 1),
    }
