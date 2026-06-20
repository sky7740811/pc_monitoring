from statistics import mean, stdev


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

    # ─── History-based analysis ───
    cpu_hist = [h['cpu']['percent'] for h in history]
    gpu_hist = [h['gpu']['percent'] for h in history]
    gt_hist = [h['gpu'].get('temp', 0) for h in history]
    mem_hist = [h['memory']['percent'] for h in history]

    # ─── 1. Bottleneck duration & frequency ───
    # Count bottleneck in recent history
    gpu_bn_count = sum(1 for h in history if h['gpu']['percent'] > 90 and h['cpu']['percent'] < 60)
    cpu_bn_count = sum(1 for h in history if h['cpu']['percent'] > 85 and h['gpu']['percent'] < 70)

    # ─── 2. Temperature trend ───
    if len(gt_hist) >= 5:
        recent_temps = gt_hist[-5:]
        temp_rate = recent_temps[-1] - recent_temps[0]  # change over ~2.5s
        if temp_rate > 3 and gpu_temp > 70:
            alerts.append({
                'type': 'warning', 'icon': '📈',
                'title': 'GPU 온도 급상승',
                'message': f'GPU 온도가 2.5초간 {temp_rate:.1f}°C 상승 중 ({gpu_temp}°C)',
            })
            health -= 10

    if len(gt_hist) >= 3:
        recent = gt_hist[-3:]
        if recent[-1] > 75 and recent[0] < 70 and (recent[-1] - recent[0]) > 5:
            alerts.append({
                'type': 'warning', 'icon': '🌡️',
                'title': 'GPU 온도 급등 감지',
                'message': f'GPU 온도가 빠르게 상승 중: {recent[0]:.0f}°C → {recent[-1]:.0f}°C',
            })
            health -= 8

    # ─── 3. Load stability (fluctuation) ───
    if len(cpu_hist) >= 10:
        cpu_sigma = stdev(cpu_hist[-10:]) if len(set(cpu_hist[-10:])) > 1 else 0
        if cpu_sigma > 20:
            alerts.append({
                'type': 'info', 'icon': '📊',
                'title': 'CPU 사용량 변동 심함',
                'message': f'CPU 편차 {cpu_sigma:.0f}% — 순간 부하 변화가 큽니다',
            })
            health -= 5

    if len(gpu_hist) >= 10:
        gpu_sigma = stdev(gpu_hist[-10:]) if len(set(gpu_hist[-10:])) > 1 else 0
        if gpu_sigma > 25:
            alerts.append({
                'type': 'info', 'icon': '📊',
                'title': 'GPU 사용량 변동 심함',
                'message': f'GPU 편차 {gpu_sigma:.0f}% — 프레임 시간 불안정 가능성',
            })
            health -= 5

    # ─── 4. Bottleneck frequency alarm ───
    if gpu_bn_count >= 5 and len(history) >= 20:
        ratio = gpu_bn_count / len(history) * 100
        alerts.append({
            'type': 'warning', 'icon': '🔁',
            'title': 'GPU 병목 반복',
            'message': f'최근 {len(history)}회 중 {gpu_bn_count}회 GPU 병목 ({ratio:.0f}%) — 지속적 GPU 부하',
        })
        if bottleneck is None:
            bottleneck = 'GPU'
        health -= 10

    if cpu_bn_count >= 5 and len(history) >= 20:
        ratio = cpu_bn_count / len(history) * 100
        alerts.append({
            'type': 'warning', 'icon': '🔁',
            'title': 'CPU 병목 반복',
            'message': f'최근 {len(history)}회 중 {cpu_bn_count}회 CPU 병목 ({ratio:.0f}%) — CPU 성능 부족',
        })
        if bottleneck is None:
            bottleneck = 'CPU'
        health -= 10

    # ─── 5. Combined resource pressure ───
    if gpu_load > 80 and mem_pct > 80:
        alerts.append({
            'type': 'warning', 'icon': '⚠️',
            'title': 'GPU + 메모리 동시 부하',
            'message': f'GPU {gpu_load}% + RAM {mem_pct}% — 둘 다 높음, 시스템 안정성 ↓',
        })
        health -= 10

    if gpu_temp > 75 and gpu_load > 85:
        alerts.append({
            'type': 'warning', 'icon': '🔥',
            'title': 'GPU 고온 + 고부하',
            'message': f'GPU {gpu_temp}°C + 사용률 {gpu_load}% — 온도 관리 권장',
        })
        health -= 10

    # ─── 6. Rapid load change (spike detection) ───
    if len(cpu_hist) >= 2:
        cpu_delta = cpu_load - cpu_hist[-1]
        if cpu_delta > 30 and cpu_load > 70:
            alerts.append({
                'type': 'info', 'icon': '⚡',
                'title': 'CPU 부하 급증',
                'message': f'CPU {cpu_hist[-1]:.0f}% → {cpu_load:.0f}% (순간 {cpu_delta:.0f}%p↑)',
            })
            health -= 3

    if len(gpu_hist) >= 2:
        gpu_delta = gpu_load - gpu_hist[-1]
        if gpu_delta > 30 and gpu_load > 70:
            alerts.append({
                'type': 'info', 'icon': '⚡',
                'title': 'GPU 부하 급증',
                'message': f'GPU {gpu_hist[-1]:.0f}% → {gpu_load:.0f}% (순간 {gpu_delta:.0f}%p↑)',
            })
            health -= 3

    # ─── 7. Existing single-point checks (kept from original) ───
    # GPU bottleneck (single point)
    if gpu_load > 90 and cpu_load < 60:
        alerts.append({
            'type': 'warning', 'icon': '🎮',
            'title': 'GPU 병목',
            'message': f'GPU {gpu_load}% · CPU {cpu_load}% → 그래픽 옵션 낮춤',
        })
        if bottleneck is None:
            bottleneck = 'GPU'
        health -= 20

    # CPU bottleneck (single point)
    elif cpu_load > 85 and gpu_load < 70:
        alerts.append({
            'type': 'warning', 'icon': '⚙️',
            'title': 'CPU 병목',
            'message': f'CPU {cpu_load}% · GPU {gpu_load}% → 백그라운드 앱 종료',
        })
        if bottleneck is None:
            bottleneck = 'CPU'
        health -= 20

    # VRAM
    if vram_pct > 90:
        alerts.append({
            'type': 'warning', 'icon': '🖼️',
            'title': 'VRAM 부족',
            'message': f'VRAM {vram_pct}% → 텍스처 품질 낮춤',
        })
        health -= 15

    # CPU temp
    if cpu_temp is not None:
        if cpu_temp > 90:
            alerts.append({
                'type': 'danger', 'icon': '🔥',
                'title': 'CPU 온도 위험',
                'message': f'CPU {cpu_temp}°C! 쓰로틀링 발생 가능',
            })
            health -= 25
        elif cpu_temp > 80:
            alerts.append({
                'type': 'warning', 'icon': '🌡️',
                'title': 'CPU 온도 주의',
                'message': f'CPU {cpu_temp}°C',
            })
            health -= 10

    # GPU temp
    if gpu_temp > 85:
        alerts.append({
            'type': 'danger', 'icon': '🔥',
            'title': 'GPU 온도 위험',
            'message': f'GPU {gpu_temp}°C!',
        })
        health -= 20
    elif gpu_temp > 75:
        alerts.append({
            'type': 'warning', 'icon': '🌡️',
            'title': 'GPU 온도 주의',
            'message': f'GPU {gpu_temp}°C',
        })
        health -= 5

    # RAM pressure
    if mem_pct > 90:
        alerts.append({
            'type': 'warning', 'icon': '🧠',
            'title': '메모리 부족',
            'message': f'RAM {mem_pct}% → 스터터링 가능',
        })
        health -= 15

    # Thermal throttling
    if cpu_temp is not None and cpu_temp > 90 and cpu_load < 50:
        alerts.append({
            'type': 'danger', 'icon': '⚠️',
            'title': '쓰로틀링 의심',
            'message': 'CPU 온도 ↑ + 사용률 ↓ = 쓰로틀링',
        })
        health -= 25

    # Low clock
    cpu_freq = cpu.get('freq')
    if cpu_freq and cpu_freq < 2.0 and cpu_load > 50:
        alerts.append({
            'type': 'info', 'icon': '📉',
            'title': '클럭 저하',
            'message': f'CPU 클럭 {cpu_freq}GHz',
        })
        health -= 5

    # ─── 8. Success case ───
    if not alerts:
        if cpu_load > 30 or gpu_load > 30:
            alerts.append({
                'type': 'success', 'icon': '✅',
                'title': '정상',
                'message': '모든 지표 정상',
            })
        else:
            alerts.append({
                'type': 'success', 'icon': '💤',
                'title': '저부하',
                'message': '시스템 여유',
            })
        health = max(health, 85)

    health = max(0, min(100, health))

    return {
        'health_score': health,
        'bottleneck': bottleneck,
        'alerts': alerts,
    }
