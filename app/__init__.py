import os
from flask import Flask, jsonify, request
from app.config import Config
from app.database import db

def create_app(config_class=Config):
    flask_app = Flask(
        __name__, 
        template_folder="templates", 
        static_folder="static"
    )
    flask_app.config.from_object(config_class)
    if os.environ.get("TRUST_PROXY") == "1":
        from werkzeug.middleware.proxy_fix import ProxyFix
        flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_proto=1)

    # 確保上傳路徑存在
    os.makedirs(flask_app.config["UPLOAD_FOLDER"], exist_ok=True)

    # 註冊外掛套件
    @flask_app.errorhandler(413)
    def too_large(error):
        return jsonify(error="上傳總量不可超過 32 MB"), 413

    @flask_app.errorhandler(ValueError)
    def invalid_input(error):
        db.session.rollback()
        return jsonify(error=str(error)), 400

    @flask_app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if response.content_type.startswith("application/json"):
            response.headers["Cache-Control"] = "no-store"
        return response
    db.init_app(flask_app)
    from app.device_guard import install_device_guard
    install_device_guard(flask_app)

    @flask_app.before_request
    def check_origin():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                return jsonify(error="不接受跨網站操作"), 403

    # 註冊 Blueprints (Views)
    from app.views.web_view import web_bp
    from app.views.api_view import api_bp
    from app.views.auth_view import auth_bp
    flask_app.register_blueprint(web_bp)
    flask_app.register_blueprint(api_bp)
    flask_app.register_blueprint(auth_bp)
    from app.views.connection_view import connection_bp
    flask_app.register_blueprint(connection_bp)

    # 建立資料表
    with flask_app.app_context():
        from app import models  # noqa
        db.create_all()
        from app.models.user import User, DeviceToken
        from app.credentials import encrypt, decrypt
        from app.models.connection import ModelConnection
        import hashlib
        for user in User.query.filter(User.gemini_api_key.isnot(None)).all():
            if user.gemini_api_key:
                user.gemini_api_key = encrypt(decrypt(user.gemini_api_key))
        for connection in ModelConnection.query.all():
            connection.api_key = encrypt(decrypt(connection.api_key))
        for device in DeviceToken.query.all():
            if len(device.token) != 64 or any(c not in "0123456789abcdef" for c in device.token):
                device.token = hashlib.sha256(device.token.encode()).hexdigest()
        db.session.commit()

    return flask_app
