"""CPU temperature via LibreHardwareMonitor pythonnet."""
import os
import sys
import time

LHM_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'librehw')
_cache = None
_cache_time = 0
_computer = None


def _init():
    global _computer
    if _computer is not None:
        return True
    dll = os.path.join(LHM_DIR, 'LibreHardwareMonitorLib.dll')
    if not os.path.isfile(dll):
        return False
    try:
        import clr
        sys.path.insert(0, LHM_DIR)
        clr.AddReference('LibreHardwareMonitorLib')
        from LibreHardwareMonitor.Hardware import Computer  # noqa
        _computer = Computer()
        _computer.IsCpuEnabled = True
        _computer.Open()
        return True
    except Exception:
        return False


def get_cpu_temp():
    global _cache, _cache_time
    now = time.time()
    if now - _cache_time < 10 and _cache is not None:
        return _cache
    _cache_time = now

    if not _init():
        return None

    try:
        for hw in _computer.Hardware:
            hw.Update()
            for s in hw.Sensors:
                st = str(s.SensorType)
                if st == 'Temperature' and s.Value and float(s.Value) > 0:
                    _cache = round(float(s.Value), 1)
                    return _cache
    except Exception:
        pass
    return None


def stop():
    global _computer
    if _computer:
        try:
            _computer.Close()
        except Exception:
            pass
        _computer = None
