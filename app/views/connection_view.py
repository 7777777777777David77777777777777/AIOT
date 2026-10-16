import re
import requests
from flask import Blueprint, request, session, jsonify
from app.database import db
from app.models.user import User
from app.models.connection import ModelConnection
from app.credentials import encrypt, decrypt

connection_bp = Blueprint("connections", __name__, url_prefix="/api/connections")


def list_models(key):
    results = []
    page = None
    try:
        for _ in range(20):
            params = {"pageSize": 1000}
            if page:
                params["pageToken"] = page
            response = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                                    headers={"x-goog-api-key": key}, params=params, timeout=20)
            if response.status_code != 200:
                if response.status_code in (400, 401):
                    raise ValueError("金鑰無效或已失效，請確認貼上完整的 Gemini API Key")
                if response.status_code == 403:
                    raise ValueError("這組金鑰沒有存取權限，請檢查 Google 專案與 API 設定")
                if response.status_code == 429:
                    raise ValueError("讀取模型清單過於頻繁，請稍後再試")
                raise ValueError("Gemini 模型清單暫時無法讀取，請稍後再試")
            data = response.json()
            for model in data.get("models", []):
                name = model.get("name", "").removeprefix("models/")
                if (re.fullmatch(r"gemini-[a-zA-Z0-9.\-]+", name)
                        and "generateContent" in model.get("supportedGenerationMethods", [])
                        and any(kind in name for kind in ("flash", "pro"))
                        and not any(kind in name for kind in ("image", "tts", "audio", "live", "robotics"))):
                    results.append({"id": name, "name": model.get("displayName", name)})
            page = data.get("nextPageToken")
            if not page:
                return results
        raise ValueError("模型清單過長，請稍後重試")
    except requests.exceptions.ConnectionError:
        raise ValueError("後端無法連線 Google API，請檢查伺服器網路或防火牆後重試") from None
    except (requests.RequestException, TypeError, KeyError):
        raise ValueError("模型服務暫時無法連線，請稍後重試") from None


@connection_bp.before_request
def require_session():
    if not session.get("user_id"):
        return jsonify(error="請先登入"), 401


def current_key(data):
    key = str(data.get("api_key", "")).strip()
    if not key:
        user = db.session.get(User, session["user_id"])
        key = decrypt(user.gemini_api_key)
    if not key:
        raise ValueError("請輸入 Gemini API Key")
    return key


@connection_bp.route("/models", methods=["POST"])
def available_models():
    return jsonify(models=list_models(current_key(request.get_json(silent=True) or {})))


@connection_bp.route("", methods=["GET", "POST"])
def connections():
    uid = session["user_id"]
    if request.method == "GET":
        return jsonify(connections=[c.to_dict() for c in ModelConnection.query.filter_by(user_id=uid).order_by(ModelConnection.created_at.desc()).all()])
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    model = str(data.get("model", ""))
    if not name or len(name) > 64:
        raise ValueError("請填寫 1 至 64 字的設定名稱")
    key = current_key(data)
    if model not in {m["id"] for m in list_models(key)}:
        raise ValueError("請重新讀取並選擇可用模型")
    ModelConnection.query.filter_by(user_id=uid).update({"active": False})
    connection = ModelConnection(user_id=uid, name=name, model=model, api_key=encrypt(key), active=True)
    db.session.add(connection)
    db.session.get(User, uid).gemini_api_key = encrypt(key)
    db.session.commit()
    return jsonify(connection=connection.to_dict())


@connection_bp.route("/<int:connection_id>/activate", methods=["POST"])
def activate(connection_id):
    uid = session["user_id"]
    connection = ModelConnection.query.filter_by(id=connection_id, user_id=uid).first()
    if not connection:
        return jsonify(error="找不到此設定"), 404
    if connection.model not in {m["id"] for m in list_models(decrypt(connection.api_key))}:
        raise ValueError("此設定的模型已無法使用，請新增設定")
    ModelConnection.query.filter_by(user_id=uid).update({"active": False})
    connection.active = True
    db.session.get(User, uid).gemini_api_key = connection.api_key
    db.session.commit()
    return jsonify(connection=connection.to_dict())
