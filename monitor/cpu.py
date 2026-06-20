import subprocess

import psutil


def prime():
    psutil.cpu_percent(interval=None, percpu=True)


def get_cpu_info():
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    percent = sum(per_core) / len(per_core) if per_core else 0.0
    freq = psutil.cpu_freq()
    cores = psutil.cpu_count()

    info = {
        'percent': round(percent, 1),
        'per_core': [round(p, 1) for p in per_core],
        'cores': cores or 0,
        'freq': round(freq.current / 1000, 2) if freq else None,
    }

    temp = _get_cpu_temp()
    if temp is not None:
        info['temp'] = temp

    return info


def _get_cpu_temp():
    try:
        result = subprocess.run(
            ['powershell', '-Command',
             'Get-CimInstance -Namespace root/WMI -ClassName MSAcpi_ThermalZoneTemperature '
             '| Select-Object -ExpandProperty CurrentTemperature'],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            temps = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    temp_k = int(line) / 10.0
                    temps.append(round(temp_k - 273.15, 1))
                except ValueError:
                    continue
            if temps:
                return max(temps)
    except Exception:
        pass
    return None
