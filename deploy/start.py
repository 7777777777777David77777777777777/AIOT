"""Render container entrypoint: Apache/PHP public, Gunicorn private."""
import os
from pathlib import Path


def prepare():
    port = int(os.environ.get("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid PORT")
    data = Path(os.environ.setdefault("DATA_DIR", "/var/data"))
    sessions = data / "php-sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    os.chmod(sessions, 0o700)
    import pwd
    user = pwd.getpwnam("www-data")
    os.chown(sessions, user.pw_uid, user.pw_gid)
    os.environ["PYTHON_API_URL"] = "http://127.0.0.1:5001"
    os.environ["TRUST_PROXY"] = "1"
    os.environ.setdefault("COOKIE_SECURE", "1")
    import sys
    sys.path.insert(0, '/app')
    from app import create_app
    create_app()  # Initialize tables once before starting API and worker processes.
    Path("/etc/apache2/ports.conf").write_text(f"Listen {port}\n")
    Path("/etc/apache2/sites-enabled/000-default.conf").write_text(f'''<VirtualHost *:{port}>
    ServerName localhost
    DocumentRoot /app/web
    SetEnvIf X-Forwarded-Proto "^https$" HTTPS=on
    SetEnvIf Authorization "^(.*)$" HTTP_AUTHORIZATION=$1
    PassEnv PYTHON_API_URL
    <Directory /app/web>
        AllowOverride All
        Require all granted
        Options -Indexes
    </Directory>
    php_value session.save_path "{sessions}"
    Timeout 120
    ErrorLog /proc/self/fd/2
    CustomLog /proc/self/fd/1 combined
</VirtualHost>
''')
    os.execvp("supervisord", ["supervisord", "-n", "-c", "/app/deploy/supervisord.conf"])


if __name__ == "__main__":
    prepare()
