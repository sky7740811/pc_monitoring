import ctypes, os, subprocess, sys, time, urllib.request

HOST, PORT = '127.0.0.1', 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
HW = ctypes.windll.user32.ShowWindow
GC = ctypes.windll.kernel32.GetConsoleWindow

def free_port():
    try:
        import psutil
        for c in psutil.net_connections():
            if c.laddr.port == PORT and c.status == 'LISTEN':
                psutil.Process(c.pid).terminate(); time.sleep(1)
    except: pass

def wait_for_server(t=20):
    for _ in range(t * 2):
        try:
            r = urllib.request.urlopen(f'http://{HOST}:{PORT}/health', timeout=2)
            if r.status == 200: r.read(); return True
        except: time.sleep(0.5)
    return False

# Show startup messages
hcon = GC()
print(' Starting server...', flush=True)

free_port()
py = sys.executable.replace('pythonw.exe', 'python.exe')
proc = subprocess.Popen(
    [py, '-m', 'uvicorn', 'main:app', '--host', HOST, '--port', str(PORT), '--log-level', 'warning'],
    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if not wait_for_server():
    print(' FAILED: Server could not start', flush=True)
    hw = GC()
    if hw: HW(hw, 5)  # restore console
    input(' Press Enter to exit...')
    proc.terminate(); sys.exit(1)

print(' Server ready! Opening window...', flush=True)
if hcon: HW(hcon, 0)  # hide console

try:
    import webview
    webview.create_window(title='PC Monitor', url=f'http://{HOST}:{PORT}', width=700, height=900, resizable=True, min_size=(380, 500))
    webview.start()
except:
    import webbrowser
    webbrowser.open(f'http://{HOST}:{PORT}')
    while True: time.sleep(1)

proc.terminate(); proc.wait()
