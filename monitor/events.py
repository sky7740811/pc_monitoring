import time

WATCH = {'LeagueClient.exe', 'LeagueClientUx.exe', 'LeagueClientUxRender.exe',
         'VALORANT.exe', 'RiotClientServices.exe',
         'Steam.exe', 'Battle.net.exe', 'EpicGamesLauncher.exe'}

_proc_track = {}  # {name: first_seen_time}
_idle_sent = set()

IDLE_MIN = 15
IDLE_CPU = 10
IDLE_RAM = 500


def check_idle(processes):
    events = []
    now = time.time()
    for p in processes:
        name = p['name']
        if name not in WATCH:
            continue
        if name not in _proc_track:
            _proc_track[name] = now
            continue
        elapsed = now - _proc_track[name]
        mins = int(elapsed // 60)
        if mins >= IDLE_MIN and (p['cpu_percent'] > IDLE_CPU or p['memory_mb'] > IDLE_RAM):
            key = name + '_idle'
            if key not in _idle_sent:
                _idle_sent.add(key)
                events.append({
                    'type': 'idle', 'icon': '\U0001f4a4',
                    'msg': f'{name} {mins}분째 실행 중 (CPU {p["cpu_percent"]}% \u00b7 RAM {p["memory_mb"]}MB)'
                })
    return events


def check(data, history):
    events = []
    cpu = data['cpu']
    gpu = data['gpu']
    mem = data['memory']
    gt = gpu.get('temp', 0)
    ct = cpu.get('temp')
    gl = gpu.get('percent', 0)
    cl = cpu.get('percent', 0)
    vp = gpu.get('vram_percent', 0)
    mp = mem.get('percent', 0)

    if gt > 85:
        events.append({'type': 'danger', 'icon': '\U0001f525', 'msg': f'GPU {gt}°C — 온도 위험!'})
    elif gt > 75:
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F', 'msg': f'GPU {gt}°C — 온도 주의'})
    if ct and ct > 90:
        events.append({'type': 'danger', 'icon': '\U0001f525', 'msg': f'CPU {ct}°C — 온도 위험!'})

    if gl > 90 and cl < 60:
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F', 'msg': f'GPU 병목 (GPU {gl}% · CPU {cl}%)'})
    elif cl > 85 and gl < 70:
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F', 'msg': f'CPU 병목 (CPU {cl}% · GPU {gl}%)'})

    if vp > 90:
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F', 'msg': f'VRAM {vp}% — 텍스처 품질 낮추세요'})
    if mp > 90:
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F', 'msg': f'RAM {mp}% — 메모리 부족'})
    if ct and ct > 90 and cl < 50:
        events.append({'type': 'danger', 'icon': '\U0001f525', 'msg': f'쓰로틀링 의심 (CPU {ct}°C + 사용률 {cl}%)'})

    if not events:
        events.append({'type': 'success', 'icon': '\u2705', 'msg': '정상 작동 중'})

    return events
