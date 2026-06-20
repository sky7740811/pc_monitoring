import asyncio
import json
import logging
import os
import webbrowser
from pathlib import Path

import psutil

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from monitor.collector import SystemCollector

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pc-monitor.log')
logging.basicConfig(
    filename=log_file, level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger('pc-monitor')

app = FastAPI()
collector = SystemCollector()
STATIC_DIR = Path(__file__).parent / 'static'


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections = [c for c in self.connections if c != ws]

    async def broadcast(self, data: dict):
        msg = json.dumps(data, default=str)
        for conn in self.connections.copy():
            try:
                await conn.send_text(msg)
            except Exception:
                self.disconnect(conn)


manager = ConnectionManager()

app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


@app.get('/')
async def index():
    return FileResponse(str(STATIC_DIR / 'index.html'))


@app.get('/health')
async def health():
    return {'status': 'ok'}


@app.post('/kill/{pid}')
async def kill_process(pid: int):
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        logger.info(f'Killed: {name} (pid={pid})')
        return {'ok': True, 'name': name}
    except psutil.NoSuchProcess:
        return {'ok': False, 'error': 'not found'}
    except psutil.AccessDenied:
        return {'ok': False, 'error': 'access denied'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


@app.post('/stop')
async def stop():
    logger.info('Shutdown requested from dashboard')
    asyncio.create_task(_shutdown())


async def _shutdown():
    await asyncio.sleep(0.3)
    try:
        s = collector.get_summary()
        top5_cpu = collector.get_process_top5('cpu')
        top5_ram = collector.get_process_top5('ram')
        top5_gpu = collector.get_process_top5('gpu')
        logs = collector.log_buffer

        w = s['warnings']; d = s['dangers']

        # --- Diagnostic humain ---
        diag_parts = []

        # CPU
        ca, cm = s['cpu_avg'], s['cpu_max']
        if cm > 90:
            diag_parts.append(f'CPU가 최대 {cm}%까지 치솟았습니다. 게임 중 CPU 부하가 상당했습니다.')
        elif ca > 70:
            diag_parts.append(f'CPU 평균 {ca}%로 부하가 높은 편입니다.')
        elif ca < 30:
            diag_parts.append(f'CPU는 평균 {ca}%로 여유롭게 동작했습니다.')
        else:
            diag_parts.append(f'CPU는 평균 {ca}%로 무난하게 동작했습니다.')

        # GPU
        ga, gm = s['gpu_avg'], s['gpu_max']
        if gm > 95:
            diag_parts.append(f'GPU가 최대 {gm}%까지 사용되었습니다. GPU 거의 풀가동.')
        elif ga > 80:
            diag_parts.append(f'GPU 평균 {ga}%로 게임이 GPU를 꽤 활용했습니다.')
        else:
            diag_parts.append(f'GPU는 평균 {ga}% 사용되었습니다.')

        # Temp
        gt_max = s['gpu_temp_max']
        if gt_max > 85:
            diag_parts.append(f'GPU 온도가 최대 {gt_max}°C까지 올라갔습니다. 온도 관리가 필요합니다!')
        elif gt_max > 75:
            diag_parts.append(f'GPU 최고 온도는 {gt_max}°C였습니다.')
        else:
            diag_parts.append(f'GPU 온도는 최대 {gt_max}°C로 안정적이었습니다.')

        # RAM
        mr = s['mem_avg']
        if mr > 85:
            diag_parts.append(f'RAM 사용률 평균 {mr}%로 메모리가 꽉 찼습니다. 닫지 않은 프로그램을 확인하세요.')
        elif mr > 70:
            diag_parts.append(f'RAM 평균 {mr}% 사용.')
        else:
            diag_parts.append(f'RAM은 평균 {mr}% 사용으로 넉넉했습니다.')

        # Alerts
        if d > 0 or w > 0:
            danger_events = [e['msg'] for e in logs if e['type'] == 'danger']
            warn_events = [e['msg'] for e in logs if e['type'] == 'warning']
            diag_parts.append(f'\n⚠️ 경고 {w}회 / 🔥 위험 {d}회 발생:')
            if danger_events:
                diag_parts.append(f'  위험: {danger_events[0]}')
            if warn_events:
                diag_parts.append(f'  경고: {warn_events[0]}')
        else:
            diag_parts.append(f'\n경고나 위험 없이 안정적으로 동작했습니다.')

        # Bottleneck
        bottleneck_events = [e['msg'] for e in logs if '병목' in e['msg']]
        if bottleneck_events:
            diag_parts.append(f'\n⚡ 병목 감지됨: {bottleneck_events[-1]}')

        diag = '\n'.join(diag_parts)

        # --- Build message ---
        status = '🟢 GOOD' if w == 0 and d == 0 else '🟡 WARNING' if d == 0 else '🔴 DANGER'
        def fmt_top5(title, items, thresh=50):
            if not items:
                return ''
            out = f'\n{title}:\n'
            for i, (n, v) in enumerate(items, 1):
                flag = ' ◀ 높음' if v > thresh else ''
                out += f' {i}. {n}: {v}%{flag}\n'
            out += f'    Total: {round(sum(v for _,v in items), 1)}%\n'
            return out

        msg = (
            f'📊 PC Monitor Session Report\n'
            f'⏱ {s["duration"]}  |  {status}\n'
            f'{"─"*50}\n'
            f'{diag}\n'
            f'{"─"*50}\n'
            f'CPU:   avg {s["cpu_avg"]}%  max {s["cpu_max"]}%\n'
            f'GPU:   avg {s["gpu_avg"]}%  max {s["gpu_max"]}%\n'
            f'온도:  GPU max {s["gpu_temp_max"]}°C\n'
            f'RAM:   avg {s["mem_avg"]}%\n'
            f'{"─"*50}\n'
        )
        msg += fmt_top5('Top 5 CPU', top5_cpu, 50)
        msg += fmt_top5('Top 5 RAM', top5_ram, 50)
        msg += fmt_top5('Top 5 GPU', top5_gpu, 50)

        ctypes.windll.user32.MessageBoxW(0, msg, 'PC Monitor', 0)
    except Exception as e:
        logger.error(f'Shutdown summary error: {e}')

    try:
        collector.save_html()
    except Exception as e:
        logger.error(f'Save failed: {e}')
    try:
        collector.generate_report()
    except Exception as e:
        logger.error(f'Report failed: {e}')
    os._exit(0)


@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_text()
            if msg == 'ping':
                await ws.send_text('pong')
    except WebSocketDisconnect:
        manager.disconnect(ws)


def default_data():
    return {
        'cpu': {'percent': 0, 'per_core': [], 'cores': 0, 'freq': None},
        'gpu': {'name': 'N/A', 'percent': 0, 'temp': 0,
                'vram_used': 0, 'vram_total': 0, 'vram_percent': 0, 'clock': 0},
        'memory': {'percent': 0, 'used_gb': 0, 'total_gb': 0},
        'disk': {'read_speed': 0, 'write_speed': 0},
        'network': {'download_speed': 0, 'upload_speed': 0},
        'processes': [],
        'diagnostic': {
            'health_score': 0, 'bottleneck': None,
            'alerts': [{'type': 'danger', 'icon': '⚠️', 'title': 'Data error',
                        'message': 'Cannot read system info'}],
        },
    }


async def broadcast_loop():
    try:
        collector.prime()
        logger.info('Collector primed')
    except Exception as e:
        logger.error(f'prime failed: {e}')

    while True:
        await asyncio.sleep(0.3)
        try:
            data = collector.collect()
        except Exception as e:
            logger.error(f'collect: {e}')
            data = default_data()
        try:
            await manager.broadcast(data)
        except Exception as e:
            logger.error(f'broadcast: {e}')


@app.on_event('startup')
async def startup():
    asyncio.create_task(broadcast_loop())


@app.on_event('shutdown')
async def shutdown():
    try:
        collector.save_html()
        logger.info('Session saved on shutdown')
    except Exception as e:
        try:
            # Fallback: save anyway
            p = collector.save_html()
            if p: logger.info(f'Session saved: {p}')
        except Exception:
            pass
        logger.error(f'Shutdown save failed: {e}')


if __name__ == '__main__':
    import uvicorn
    webbrowser.open('http://localhost:8765')
    logger.setLevel(logging.INFO)
    print(' PC Monitor')
    print(' Open http://localhost:8765 in your browser')
    print(' Press Ctrl+C to stop')
    uvicorn.run('main:app', host='127.0.0.1', port=8765, log_level='info')
