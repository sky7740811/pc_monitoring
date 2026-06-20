import ctypes, os, subprocess, sys, time, urllib.request

# Hide console immediately
try:
    h = ctypes.windll.kernel32.GetConsoleWindow()
    if h: ctypes.windll.user32.ShowWindow(h, 0)
except: pass

# Auto-elevate to admin (silent)
try:
    if not ctypes.windll.shell32.IsUserAnAdmin():
        script = os.path.abspath(__file__)
        py = sys.executable
        subprocess.Popen(['powershell', '-Command',
            f"Start-Process '{py}' -ArgumentList '{script}' -Verb RunAs -WindowStyle Hidden"])
        sys.exit(0)
except: pass

HOST, PORT = '127.0.0.1', 8765
ROOT = os.path.dirname(os.path.abspath(__file__))

# Disable WebView2 GPU (reduces msedgewebview2 processes)
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--disable-gpu'

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

free_port()
py = sys.executable.replace('pythonw.exe', 'python.exe')
proc = subprocess.Popen(
    [py, '-m', 'uvicorn', 'main:app', '--host', HOST, '--port', str(PORT), '--log-level', 'warning'],
    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if not wait_for_server():
    ctypes.windll.user32.MessageBoxW(0, 'Server did not start.\nTry running PC Monitor.bat first.', 'PC Monitor Error', 0)
    proc.terminate(); sys.exit(1)

try:
    import webview
    webview.create_window(title='PC Monitor', url=f'http://{HOST}:{PORT}', width=700, height=900, resizable=True, min_size=(380, 500))
    webview.start()
except:
    import webbrowser
    webbrowser.open(f'http://{HOST}:{PORT}')
    while True: time.sleep(1)

try:
    req = urllib.request.Request(f'http://{HOST}:{PORT}/stop', b'{}', {'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=5)
except: pass
time.sleep(1)
proc.terminate(); proc.wait()
