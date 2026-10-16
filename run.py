"""Start the PHP website and the private Python API together."""
import os
import shutil
import subprocess
import threading
from pathlib import Path
from app import create_app
from werkzeug.serving import make_server

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
    api = make_server('127.0.0.1', api_port, create_app(), threaded=True)
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()
    env = os.environ.copy(); env['PYTHON_API_URL'] = 'http://127.0.0.1:' + str(api_port)
    # PHP session files belong to this project and are excluded from version control.
    sessions = BASE_DIR / '.runtime' / 'sessions'; sessions.mkdir(parents=True, exist_ok=True)
    command = [php, '-d', 'session.save_path=' + str(sessions), '-d', 'upload_max_filesize=8M',
               '-d', 'post_max_size=32M', '-d', 'max_file_uploads=8', '-S', host + ':' + str(port),
               '-t', str(BASE_DIR / 'web'), str(BASE_DIR / 'web' / 'router.php')]
    process = None
    try:
        process = subprocess.Popen(command, cwd=Path(php).parent, env=env,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        print('PHP website: http://127.0.0.1:' + str(port), flush=True)
        print('Python API: private localhost port ' + str(api_port), flush=True)
        process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if process and process.poll() is None:
            process.terminate(); process.wait(timeout=5)
        api.shutdown(); api.server_close()

if __name__ == '__main__':
    main()
