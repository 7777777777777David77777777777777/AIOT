import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)

secret_path = os.path.join(DATA_DIR, ".session-secret")
if not os.path.exists(secret_path):
    import secrets
    with open(secret_path, "w") as secret_file:
        secret_file.write(secrets.token_hex(32))


def database_url(value=None):
    value = (value if value is not None else os.environ.get("DATABASE_URL", "")).strip()
    if not value:
        if os.environ.get("RENDER") == "true":
            raise RuntimeError("Render requires DATABASE_URL; refusing temporary SQLite fallback")
        return f"sqlite:///{os.path.join(DATA_DIR, 'exam_solver.db')}"
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix):]
    return value

class Config:
    ADMIN_UIDS = os.environ.get("ADMIN_UIDS", "")
    ENCRYPT_STORED_KEYS = os.environ.get("ENCRYPT_STORED_KEYS", "0") == "1"
    SECRET_KEY = os.environ.get("SECRET_KEY") or open(secret_path).read().strip()
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 圖片上傳目錄
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(DATA_DIR, "uploads"))
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB max upload
    
    # 預設 VLM 設定
    DEFAULT_MODEL = "gemini-2.5-flash"
    DEFAULT_TIMEOUT = 60

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
