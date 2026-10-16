from datetime import datetime
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import db

def generate_user_uid():
    # 隨機 6 碼大寫英數字（排除 0, O, 1, I 避免混淆）
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(secrets.choice(chars) for _ in range(6))

class User(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(10), unique=True, nullable=False, index=True) # 永久固定 6 碼身分 UID
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    gemini_api_key = db.Column(db.String(128), nullable=True) # 使用者自訂的模型 Key
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 關聯
    devices = db.relationship("DeviceToken", backref="user", cascade="all, delete-orphan", lazy=True)
    batches = db.relationship("QuestionBatch", backref="user", cascade="all, delete-orphan", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "uid": self.uid,
            "username": self.username,
            "has_api_key": bool(self.gemini_api_key),
            "created_at": self.created_at.isoformat()
        }

class DeviceToken(db.Model):
    __tablename__ = "devices"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    device_name = db.Column(db.String(64), default="ESP32-S3 Calculator")
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(32)

    def to_dict(self, include_token=False):
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "device_name": self.device_name,
            "created_at": self.created_at.isoformat(),
            "last_active_at": self.last_active_at.isoformat()
        }

        if include_token:
            result["token"] = self.issued_token
        return result
