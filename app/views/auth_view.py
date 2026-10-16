from flask import Blueprint, request, jsonify, session
from app.controllers.auth_controller import AuthController
from app.models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json or request.form
    username = data.get("username", "")
    password = data.get("password", "")

    user, error = AuthController.register(username, password)
    if error:
        return jsonify({"error": error}), 400

    session.clear()
    session["user_id"] = user.id
    return jsonify({
        "status": "success",
        "message": "註冊成功",
        "user": user.to_dict()
    })

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json or request.form
    username = data.get("username", "")
    password = data.get("password", "")

    user, error = AuthController.login(username, password)
    if error:
        return jsonify({"error": error}), 401

    session.clear()
    session["user_id"] = user.id
    return jsonify({
        "status": "success",
        "message": "登入成功",
        "user": user.to_dict()
    })

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    return jsonify({"status": "success", "message": "已登出"})

@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False, "user": None})

    user = User.query.get(user_id)
    if not user:
        session.pop("user_id", None)
        return jsonify({"authenticated": False, "user": None})

    return jsonify({
        "authenticated": True,
        "user": user.to_dict(),
        "devices": [d.to_dict() for d in user.devices]
    })

@auth_bp.route("/apikey", methods=["POST"])
def save_api_key():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "請先登入"}), 401

    data = request.json or request.form
    api_key = data.get("api_key", "").strip()

    success, error = AuthController.update_gemini_key(user_id, api_key)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"status": "success", "message": "API Key 已安全儲存於帳號中"})
