import psutil


_prev = None


def prime():
    global _prev
    _prev = psutil.net_io_counters()


def get_network_speed(dt=1.0):
    global _prev
    curr = psutil.net_io_counters()
    if _prev is None:
        _prev = curr
        return {'download_speed': 0.0, 'upload_speed': 0.0}
    down_bps = max(0, curr.bytes_recv - _prev.bytes_recv) / max(dt, 0.1)
    up_bps = max(0, curr.bytes_sent - _prev.bytes_sent) / max(dt, 0.1)
    _prev = curr
    return {
        'download_speed': round(down_bps / (1024 * 1024), 2),
        'upload_speed': round(up_bps / (1024 * 1024), 2),
    }
