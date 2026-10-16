from types import SimpleNamespace
from datetime import datetime
import hashlib
from app.models.user import DeviceToken, User
from app.database import db

class DeviceController:
    @staticmethod
    def verify_token(token_string):
        """
        驗證 Bearer Token 是否合法，並更新最後上線時間
        """
        if not token_string:
            return None
        
        code = token_string.strip().upper()
        if len(code) == 6:
            user = User.query.filter_by(uid=code).first()
            if user:
                return SimpleNamespace(user_id=user.id)
        device = DeviceToken.query.filter_by(token=hashlib.sha256(token_string.encode()).hexdigest()).first()
        if device:
            device.last_active_at = datetime.utcnow()
            db.session.commit()
            return device
        return None

    @staticmethod
    def create_device_token(user_id, device_name="ESP32-S3 Calculator"):
        """
        為使用者生成專屬隨機裝置 Token
        """
        user = User.query.get(user_id)
        if not user:
            return None
        token_str = DeviceToken.generate_token()
        device = DeviceToken(user_id=user_id, device_name=device_name, token=hashlib.sha256(token_str.encode()).hexdigest())
        db.session.add(device)
        db.session.commit()
        device.issued_token = token_str
        return device
