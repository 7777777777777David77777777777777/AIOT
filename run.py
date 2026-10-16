"""Start the PHP website and the private Python API together."""
import os
import shutil
import subprocess
import sys
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def main():
    php = os.environ.get('PHP_BINARY') or str(BASE_DIR / '.runtime' / 'php' / 'php.exe')
    if not Path(php).is_file():
        php = shutil.which('php')
    if not php:
        raise SystemExit('PHP 8.2+ is required. Set PHP_BINARY to its executable path.')
    version = subprocess.check_output([php, '-r', 'echo PHP_VERSION_ID;'], text=True, cwd=Path(php).parent).strip()
    if not version.isdigit() or int(version) < 80200:
        raise SystemExit('PHP 8.2+ is required. Set PHP_BINARY to a newer PHP runtime.')
    port = int(os.environ.get('WEB_PORT', '5000'))
    api_port = int(os.environ.get('API_PORT', '5001'))
    host = os.environ.get('WEB_HOST', '127.0.0.1')
    os.environ['FRONTEND_URL'] = 'http://127.0.0.1:' + str(port)
    env = os.environ.copy(); env['PYTHON_API_URL'] = 'http://127.0.0.1:' + str(api_port)
    # PHP session files belong to this project and are excluded from version control.
    sessions = BASE_DIR / '.runtime' / 'sessions'; sessions.mkdir(parents=True, exist_ok=True)
    command = [php, '-d', 'session.save_path=' + str(sessions), '-d', 'upload_max_filesize=20M',
               '-d', 'post_max_size=128M', '-d', 'max_file_uploads=16', '-S', host + ':' + str(port),
               '-t', str(BASE_DIR / 'web'), str(BASE_DIR / 'web' / 'router.php')]
    processes = []
    try:
        options = dict(cwd=BASE_DIR, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        api = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'asgi:app', '--host', '127.0.0.1', '--port', str(api_port)], **options)
        processes.append(api)
        for _ in range(100):
            if api.poll() is not None: raise RuntimeError('FastAPI failed to start')
            try:
                if requests.get('http://127.0.0.1:' + str(api_port) + '/api/v1/health', timeout=.3).status_code == 200: break
            except requests.RequestException: pass
            time.sleep(.1)
        else: raise RuntimeError('FastAPI startup timed out')
        worker = subprocess.Popen([sys.executable, 'worker.py'], **options); processes.append(worker)
        php_process = subprocess.Popen(command, cwd=Path(php).parent, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)); processes.append(php_process)
        print('PHP website: http://127.0.0.1:' + str(port), flush=True)
        print('FastAPI: http://127.0.0.1:' + str(api_port) + '/api/docs', flush=True)
        print('Persistent task worker started', flush=True)
        while all(p.poll() is None for p in processes): time.sleep(.5)
        raise RuntimeError('A service stopped; shutting down the remaining services')
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait()

if __name__ == '__main__':
    main()
