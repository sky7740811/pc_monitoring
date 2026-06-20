import os
import struct

import psutil

_desc_cache = {}


def _get_file_desc(filepath):
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        import win32api
        trans = win32api.GetFileVersionInfo(filepath, '\\VarFileInfo\\Translation')
        if isinstance(trans, (tuple, list)):
            if trans:
                entry = trans[0]
                if isinstance(entry, (tuple, list)):
                    lang, cp = entry
                elif isinstance(entry, bytes):
                    lang, cp = struct.unpack('<HH', entry[:4])
                else:
                    return None
                sub = f'\\StringFileInfo\\{lang:04x}{cp:04x}\\FileDescription'
                desc = win32api.GetFileVersionInfo(filepath, sub)
                if desc and isinstance(desc, str):
                    return desc.strip()
    except Exception:
        pass
    return None


def get_top_processes(n=8):
    processes = []
    skip = {'System Idle Process', 'System', 'Registry', 'smss.exe',
            'Secure System', 'Memory Compression'}
    cores = psutil.cpu_count() or 1
    try:
        iter_proc = psutil.process_iter(['name', 'pid', 'cpu_percent', 'memory_info', 'exe'])
        for proc in iter_proc:
            try:
                info = proc.info
                if info['name'] in skip:
                    continue
                if info['name'] and info['cpu_percent'] is not None:
                    name = info['name']
                    if name not in _desc_cache:
                        desc = _get_file_desc(info.get('exe'))
                        _desc_cache[name] = desc if desc else name
                    display_name = _desc_cache[name]
                    mem_mb = (info['memory_info'].rss / (1024 * 1024)
                              if info['memory_info'] else 0)
                    processes.append({
                        'name': name,
                        'display_name': display_name,
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
