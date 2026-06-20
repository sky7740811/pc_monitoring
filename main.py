import asyncio
import json
import logging
import os
import webbrowser
from pathlib import Path

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


@app.post('/stop')
async def stop():
    logger.info('Shutdown requested from dashboard')
    asyncio.create_task(_shutdown())


async def _shutdown():
    await asyncio.sleep(0.3)
    try:
        path = collector.save_html()
        logger.info(f'Session saved: {path}')
    except Exception as e:
        logger.error(f'Save failed: {e}')
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
        await asyncio.sleep(1)
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


if __name__ == '__main__':
    import uvicorn
    webbrowser.open('http://localhost:8765')
    logger.setLevel(logging.INFO)
    print(' PC Monitor')
    print(' Open http://localhost:8765 in your browser')
    print(' Press Ctrl+C to stop')
    uvicorn.run('main:app', host='127.0.0.1', port=8765, log_level='info')
