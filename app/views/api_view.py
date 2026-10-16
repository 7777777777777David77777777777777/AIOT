import os
import json
from flask import Blueprint, request, jsonify, send_from_directory, session, current_app
from app.config import Config
from app.credentials import decrypt
from app.database import db
from app.models.question import QuestionBatch, Photo, Message
from app.models.user import User, DeviceToken
from app.controllers.photo_controller import PhotoController
from app.controllers.solver_controller import SolverController
from app.controllers.device_controller import DeviceController

def authenticated_user():
    if session.get("user_id"):
        return session["user_id"]
    header = request.headers.get("Authorization", "")
    device = DeviceController.verify_token(header[7:]) if header.startswith("Bearer ") else None
    return device.user_id if device else None

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/health")
def health():
    from sqlalchemy import text
    db.session.execute(text("SELECT 1"))
    return jsonify(ok=True)

@api_bp.route("/uploads/<filename>")
def serve_uploaded_file(filename):
    """
    提供已上傳圖片存取
    """
    user_id = authenticated_user()
    photo = Photo.query.filter_by(filename=filename).first()
    from app.models.admin import is_admin
    admin = session.get('user_id') and is_admin(session['user_id'])
    if not user_id or not photo or (photo.batch.user_id != user_id and not admin):
        return jsonify({"error": "找不到此圖片"}), 404
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

@api_bp.route("/upload", methods=["POST"])
def upload_single_photo():
    """
    單圖上傳端點（符合 ESP32-S3 逐張上傳與釋放 Buffer 架構）
    回傳 photo_id 與 batch_id
    """
    user_id = authenticated_user()
    if not user_id:
        return jsonify({"error": "請先登入或提供有效裝置 Token"}), 401

    file = request.files.get("photo") or request.files.get("image")
    if not file:
        return jsonify({"error": "未提供圖片檔案"}), 400

    batch_id = request.form.get("batch_id")
    if not batch_id:
        batch = QuestionBatch(
            user_id=user_id,
            status="queued"
        )
        db.session.add(batch)
        db.session.commit()
        batch_id = batch.id
    else:
        batch = QuestionBatch.query.get(batch_id)
        if not batch or batch.user_id != user_id:
            return jsonify({"error": "找不到此題目"}), 404

    photo = PhotoController.save_photo(file, batch_id)
    if not photo:
        return jsonify({"error": "圖片儲存失敗"}), 500

    return jsonify({
        "status": "success",
        "batch_id": batch_id,
        "photo_id": photo.id,
        "filename": photo.filename,
        "url": f"/api/uploads/{photo.filename}"
    })

@api_bp.route("/solve", methods=["POST"])
def solve():
    """
    解題端點：可接收表單上傳的多張圖，或傳入既有 batch_id 觸發解答
    """
    batch_id = request.form.get("batch_id")
    batch = QuestionBatch.query.get(batch_id) if batch_id else None

    user_id = authenticated_user()
    if not user_id:
        return jsonify({"error": "請先登入或提供有效裝置 Token"}), 401
    if batch_id and (not batch or batch.user_id != user_id):
        return jsonify({"error": "找不到此題目"}), 404
    logged_user = User.query.get(user_id) if user_id else None

    api_key = (
        request.headers.get("X-API-Key")
        or request.form.get("api_key")
        or (decrypt(logged_user.gemini_api_key) if logged_user and logged_user.gemini_api_key else None)
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )

    if not api_key:
        return jsonify({"error": "請提供 Gemini API Key！可在右上角設定或登入帳號儲存。"}), 400

    if request.form.get("prompt", "").strip():
        return jsonify({"error": "此聊天室僅接受題目照片，不支援文字訊息"}), 400
    uploaded_files = request.files.getlist("images") + request.files.getlist("images[]")
    if batch and batch.status != "queued" and not uploaded_files:
        return jsonify({"error": "請加入照片後再送出"}), 400
    if not batch and not uploaded_files:
        return jsonify({"error": "請先上傳題目照片"}), 400
    if len(uploaded_files) + (len(batch.photos) if batch else 0) > 8:
        return jsonify({"error": "同一對話最多 8 張題目照片，請另開新對話"}), 400
    prompt = "請依照片題號解題，以參考解答卷的格式精簡呈現解法與答案。"
    from app.models.connection import ModelConnection
    connection = ModelConnection.query.filter_by(user_id=user_id, active=True).first()
    model_name = connection.model if connection else Config.DEFAULT_MODEL
    history = [{"role": m.role, "content": m.content} for m in batch.messages[-6:]] if batch else []

    if batch and batch.status == "solving":
        return jsonify({"error": "此題目正在解題，請稍候"}), 409

    if batch:
        if user_id and not batch.user_id:
            batch.user_id = user_id
            db.session.commit()
    else:
        batch = QuestionBatch(user_id=user_id, status="queued", prompt=prompt)
        db.session.add(batch)
        db.session.commit()
        batch_id = batch.id

    # 處理隨本次請求上傳的圖片
    for f in uploaded_files:
        PhotoController.save_photo(f, batch_id)

    batch.prompt = "照片題目 · {} 張".format(len(batch.photos))
    db.session.commit()

    # 取出此 batch 關聯的所有照片
    photos = Photo.query.filter_by(batch_id=batch_id).all()

    if not photos:
        return jsonify({"error": "請先上傳題目照片"}), 400

    try:
        result = SolverController.process_solution(
            batch_id=batch_id,
            user_prompt=prompt,
            photo_records=photos,
            api_key=api_key,
            model_name=model_name,
            history_messages=history
        )
        first = result["questions"][0]
        batch.prompt = (first["number"] + " · " + (first["question"] or "照片需補拍"))[:64]
        db.session.commit()
        return jsonify(result)
    except Exception:
        db.session.rollback()
        batch = QuestionBatch.query.get(batch_id)
        batch.status = "failed"
        db.session.commit()
        return jsonify({"error": "解題暫時失敗，請檢查 API Key 或稍後重試"}), 502

@api_bp.route("/tasks/<task_id>/status", methods=["GET"])
def get_task_status(task_id):
    """
    查詢任務狀態（支援 ESP32 非同步輪詢）
    """
    user_id = authenticated_user()
    batch = QuestionBatch.query.get(task_id)
    if not user_id or not batch or batch.user_id != user_id:
        return jsonify({"error": "找不到此任務"}), 404

    return jsonify(batch.to_dict())

@api_bp.route("/history", methods=["GET"])
def get_history():
    """
    獲取最近解題紀錄列表（若已登入則查該使用者的記錄）
    """
    user_id = authenticated_user()
    if not user_id:
        return jsonify({"error": "請先登入"}), 401
    query = QuestionBatch.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    batches = query.order_by(QuestionBatch.created_at.desc()).limit(20).all()
    return jsonify({
        "batches": [b.to_dict() for b in batches]
    })

@api_bp.route("/device/token", methods=["POST"])
def generate_token():
    """
    為使用者生成裝置 Token（供手動輸入 ESP32-S3）
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "請先登入"}), 401
    user = db.session.get(User, user_id)
    return jsonify({"status": "success", "device": {"token": user.uid, "code": user.uid, "device_name": "固定帳號裝置碼"}})
