"""Detection d'evenements systeme avec descriptions detaillees."""

WATCH = {'LeagueClient.exe', 'LeagueClientUx.exe', 'LeagueClientUxRender.exe',
         'VALORANT.exe', 'RiotClientServices.exe',
         'Steam.exe', 'Battle.net.exe', 'EpicGamesLauncher.exe'}

_proc_track = {}
_idle_sent = set()
IDLE_MIN = 15
IDLE_CPU = 10
IDLE_RAM = 500

# Critical system processes that should never be killed
SYSTEM_PROCS = {'csrss.exe', 'wininit.exe', 'services.exe', 'lsass.exe',
                'winlogon.exe', 'smss.exe', 'System', 'Registry',
                'Memory Compression', 'Secure System', 'svchost.exe',
                'dwm.exe', 'fontdrvhost.exe', 'spoolsv.exe',
                'MsMpEng.exe', 'NisSrv.exe'}


def _top_n(data, key, n=3):
    """Return top N processes by `key`, excluding critical system ones.
    Returns list of (display_name, value)."""
    procs = [p for p in data.get('processes', []) if p['name'] not in SYSTEM_PROCS]
    sorted_procs = sorted(procs, key=lambda p: p.get(key, 0), reverse=True)
    return [(p.get('display_name', p['name']), p.get(key, 0)) for p in sorted_procs if p.get(key, 0) > 0][:n]


def _format_proc_list(procs, unit='%'):
    return ', '.join(f'{n}: {v}{unit}' for n, v in procs)


def _spike_info(data):
    """Return formatted spike message if available."""
    spike = data.get('cpu_spike')
    if not spike:
        return '', ''
    dname = spike.get('display_name', spike['name'])
    delta = spike['delta']
    msg = f'⚡ {dname} CPU +{delta}%p 급등'
    detail = f'{dname}이(가) CPU 사용량이 짧은 시간에 {delta}%p 상승했습니다.'
    return msg, detail


def check_idle(processes):
    events = []
    now = __import__('time').time()
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
                    'msg': f'{name} {mins}분째 실행 중 (CPU {p["cpu_percent"]}% \u00b7 RAM {p["memory_mb"]}MB)',
                    'detail': (
                        f'이 프로세스는 게임 종료 후에도 백그라운드에 남아 리소스를 점유하고 있습니다.\n'
                        f'CPU: {p["cpu_percent"]}% / RAM: {p["memory_mb"]}MB\n'
                        f'실행 시간: {mins}분\n\n'
                        f'권장 조치: 작업 관리자에서 해당 프로세스를 종료하거나,\n'
                        f'게임 클라이언트 설정에서 "종료 후 트레이 최소화"를 해제하세요.'
                    ),
                })
    return events


def check(data, history):
    events = []
    cpu = data['cpu']; gpu = data['gpu']; mem = data['memory']
    gt = gpu.get('temp', 0); ct = cpu.get('temp')
    gl = gpu.get('percent', 0); cl = cpu.get('percent', 0)
    vp = gpu.get('vram_percent', 0); mp = mem.get('percent', 0)

    if gt > 85:
        top_gpu = _top_n(data, 'gpu_sm')
        cause = ' (GPU 사용: ' + _format_proc_list(top_gpu) + ')' if top_gpu else ''
        events.append({'type': 'danger', 'icon': '\U0001f525',
            'msg': f'GPU {gt}°C — 온도 위험!',
            'detail': f'GPU 온도가 {gt}°C에 도달했습니다.{cause}\n'
                      f'85°C 이상은 GPU에 손상을 줄 수 있는 임계값입니다.\n\n'
                      f'권장 조치:\n'
                      f'• 게임 그래픽 옵션 낮추기 (특히 그림자/안티앨리어싱)\n'
                      f'• 케이스 환기 및 팬 속도 확인\n'
                      f'• GPU 클럭 속도 강제 제한 (MSI Afterburner)\n'
                      f'• GPU 먼지 청소 및 서멀 재도포'})
    elif gt > 75:
        top_gpu = _top_n(data, 'gpu_sm')
        cause = ' (GPU 사용: ' + _format_proc_list(top_gpu) + ')' if top_gpu else ''
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F',
            'msg': f'GPU {gt}°C — 온도 주의',
            'detail': f'GPU 온도가 {gt}°C입니다.{cause}\n'
                      f'게임 중 75°C 이상은 높은 편입니다.\n\n'
                      f'권장 조치:\n'
                      f'• 팬 속도 프로필 확인 (고정 100% 테스트)\n'
                      f'• 수직 동기화(V-Sync) 또는 FPS 제한 설정\n'
                      f'• GPU 팬 먼지 점검'})

    if ct and ct > 90:
        top_cpu = _top_n(data, 'cpu_percent')
        cause = ' (CPU 사용: ' + _format_proc_list(top_cpu) + ')' if top_cpu else ''
        events.append({'type': 'danger', 'icon': '\U0001f525',
            'msg': f'CPU {ct}°C — 온도 위험!',
            'detail': f'CPU 온도가 {ct}°C까지 올라갔습니다.{cause}\n'
                      f'쓰로틀링으로 인한 성능 저하가 발생할 수 있습니다.\n\n'
                      f'권장 조치:\n'
                      f'• CPU 쿨러 상태 확인 (공랭/수랭 펌프 작동 여부)\n'
                      f'• 서멀 그리스 재도포\n'
                      f'• CPU 전압 언더볼팅 고려\n'
                      f'• 케이스 에어플로우 개선'})

    if gl > 90 and cl < 60:
        top_gpu = _top_n(data, 'gpu_sm')
        cause = '\nGPU 사용: ' + _format_proc_list(top_gpu) if top_gpu else ''
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F',
            'msg': f'GPU 병목 (GPU {gl}% · CPU {cl}%)',
            'detail': f'GPU 사용률({gl}%)이 CPU({cl}%)보다 현저히 높습니다.{cause}\n'
                      f'GPU가 최대 성능으로 동작 중이나 CPU가 GPU를 따라가지 못하고 있습니다.\n\n'
                      f'권장 조치:\n'
                      f'• 그래픽 옵션을 낮춰 GPU 부하 감소\n'
                      f'• 해상도 낮추기\n'
                      f'• DLSS/FSR 업스케일링 활성화\n'
                      f'• CPU 오버클럭 또는 업그레이드 고려'})
    elif cl > 85 and gl < 70:
        top_cpu = _top_n(data, 'cpu_percent')
        spike_msg, spike_detail = _spike_info(data)
        cause = ''
        if spike_msg:
            cause = '\n' + spike_msg
        cause += '\nCPU 높은 프로세스:\n  ' + '\n  '.join(f'{n}: {v}%' for n, v in top_cpu) if top_cpu else ''
        detail = f'CPU 사용률({cl}%)이 GPU({gl}%)보다 현저히 높습니다.'
        if spike_detail:
            detail += '\n' + spike_detail
        detail += f'{cause}\n\n'
        detail += '위 프로세스 중 게임 외 불필요한 것을 종료하면\nCPU 병목이 완화될 수 있습니다.\n\n'
        detail += '권장 조치:\n• 위 목록에서 게임이 아닌 프로세스 종료\n'
        detail += '• 해상도/그래픽 옵션 올리기 (GPU 부하 증가)\n'
        detail += '• CPU 집중 설정(물리 효과, NPC 수 등) 낮추기\n'
        detail += '• CPU 오버클럭 검토'
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F',
            'msg': f'CPU 병목 (CPU {cl}% · GPU {gl}%)', 'detail': detail})

    if vp > 90:
        top_vram = _top_n(data, 'gpu_mem')
        cause = '\nVRAM 사용: ' + _format_proc_list(top_vram, 'MB') if top_vram else ''
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F',
            'msg': f'VRAM {vp}% — 텍스처 품질 낮추세요',
            'detail': f'VRAM 사용률이 {vp}%입니다.{cause}\n\n'
                      f'VRAM이 부족하면 시스템 RAM으로 대체되어\n'
                      f'심각한 스터터링(끊김)이 발생합니다.\n\n'
                      f'권장 조치:\n'
                      f'• 텍스처 품질 한 단계 낮추기\n'
                      f'• 그림자 품질 낮추기\n'
                      f'• 텍스처 스트리밍 옵션 확인'})

    if mp > 90:
        top_ram = _top_n(data, 'memory_mb')
        cause = '\nRAM 높은 프로세스:\n  ' + '\n  '.join(f'{n}: {v}MB' for n, v in top_ram) if top_ram else ''
        events.append({'type': 'warning', 'icon': '\u26a0\uFE0F',
            'msg': f'RAM {mp}% — 메모리 부족',
            'detail': f'시스템 메모리 사용률이 {mp}%입니다.{cause}\n\n'
                      f'권장 조치:\n'
                      f'• 위 목록에서 게임이 아닌 프로세스 종료\n'
                      f'• 가상 메모리(페이지 파일) 설정 확인\n'
                      f'• 메모리 누수가 있는 프로그램 확인'})

    if ct and ct > 90 and cl < 50:
        top_cpu = _top_n(data, 'cpu_percent')
        cause = '\nCPU 사용: ' + _format_proc_list(top_cpu) if top_cpu else ''
        events.append({'type': 'danger', 'icon': '\U0001f525',
            'msg': f'쓰로틀링 의심 (CPU {ct}°C + 사용률 {cl}%)',
            'detail': f'CPU 온도({ct}°C)는 높은데 사용률({cl}%)이 낮습니다.{cause}\n'
                      f'이는 열 쓰로틀링이 활성화되었을 가능성이 높습니다.\n'
                      f'CPU가 과열을 방지하기 위해 강제로 클럭을 낮추고 있습니다.\n\n'
                      f'권장 조치:\n'
                      f'• CPU 온도 85°C 이하로 유지 필요\n'
                      f'• 쿨러 장착 상태 재확인\n'
                      f'• 케이스 내부 공기 흐름 개선\n'
                      f'• 전원 옵션 "고성능" 확인'})

    if not events:
        events.append({'type': 'success', 'icon': '\u2705', 'msg': '정상 작동 중', 'detail': ''})

    return events
