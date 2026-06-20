def analyze(data, history):
    alerts = []
    bottleneck = None
    health = 100

    cpu = data['cpu']
    gpu = data['gpu']
    memory = data['memory']

    gpu_load = gpu.get('percent', 0)
    cpu_load = cpu.get('percent', 0)
    gpu_temp = gpu.get('temp', 0)
    cpu_temp = cpu.get('temp')
    vram_pct = gpu.get('vram_percent', 0)
    mem_pct = memory.get('percent', 0)

    # GPU bottleneck
    if gpu_load > 90 and cpu_load < 60:
        alerts.append({
            'type': 'warning', 'icon': '🎮',
            'title': 'GPU 병목',
            'message': f'GPU {gpu_load}% · CPU {cpu_load}% → 그래픽 옵션을 낮추면 FPS 향상 가능',
        })
        bottleneck = 'GPU'
        health -= 20

    # CPU bottleneck
    elif cpu_load > 85 and gpu_load < 70:
        alerts.append({
            'type': 'warning', 'icon': '⚙️',
            'title': 'CPU 병목',
            'message': f'CPU {cpu_load}% · GPU {gpu_load}% → 백그라운드 앱 종료 또는 해상도 증가',
        })
        bottleneck = 'CPU'
        health -= 20

    # VRAM pressure
    if vram_pct > 90:
        alerts.append({
            'type': 'warning', 'icon': '🖼️',
            'title': 'VRAM 부족',
            'message': f'VRAM {vram_pct}% 사용 중 → 텍스처 품질을 낮추면 스터터링 감소',
        })
        health -= 15

    # CPU temperature
    if cpu_temp is not None:
        if cpu_temp > 90:
            alerts.append({
                'type': 'danger', 'icon': '🔥',
                'title': 'CPU 온도 위험',
                'message': f'CPU {cpu_temp}°C! 쓰로틀링 발생 가능. 쿨러 상태 확인 필요',
            })
            health -= 25
        elif cpu_temp > 80:
            alerts.append({
                'type': 'warning', 'icon': '🌡️',
                'title': 'CPU 온도 주의',
                'message': f'CPU {cpu_temp}°C — 온도가 높습니다',
            })
            health -= 10

    # GPU temperature
    if gpu_temp > 85:
        alerts.append({
            'type': 'danger', 'icon': '🔥',
            'title': 'GPU 온도 위험',
            'message': f'GPU {gpu_temp}°C! 팬 속도 및 케이스 환기 확인',
        })
        health -= 20
    elif gpu_temp > 75:
        alerts.append({
            'type': 'warning', 'icon': '🌡️',
            'title': 'GPU 온도 주의',
            'message': f'GPU {gpu_temp}°C — 온도 상승 중',
        })
        health -= 5

    # RAM pressure
    if mem_pct > 90:
        alerts.append({
            'type': 'warning', 'icon': '🧠',
            'title': '메모리 부족',
            'message': f'RAM {mem_pct}% 사용 중 → 게임 스터터링 발생 가능',
        })
        health -= 15

    # Thermal throttling suspicion
    if cpu_temp is not None and cpu_temp > 90 and cpu_load < 50:
        alerts.append({
            'type': 'danger', 'icon': '⚠️',
            'title': '쓰로틀링 의심',
            'message': 'CPU 온도 높음 + 사용률 낮음 = 열 쓰로틀링 활성화 의심',
        })
        health -= 25

    # Low clock speed on load
    cpu_freq = cpu.get('freq')
    if cpu_freq and cpu_freq < 2.0 and cpu_load > 50:
        alerts.append({
            'type': 'info', 'icon': '📉',
            'title': '클럭 저하',
            'message': f'CPU 클럭 {cpu_freq}GHz — 전원 옵션을 확인하세요',
        })
        health -= 5

    # No issues
    if not alerts:
        if cpu_load > 30 or gpu_load > 30:
            alerts.append({
                'type': 'success', 'icon': '✅',
                'title': '정상',
                'message': '모든 지표 정상 범위. 쾌적한 게이밍 환경',
            })
        else:
            alerts.append({
                'type': 'success', 'icon': '💤',
                'title': '저부하',
                'message': '시스템이 여유롭게 동작 중',
            })
        health = max(health, 85)

    health = max(0, min(100, health))

    return {
        'health_score': health,
        'bottleneck': bottleneck,
        'alerts': alerts,
    }
