from app.models.user import User
from app.credentials import encrypt
from app.database import db

class AuthController:
    @staticmethod
    def register(username, password):
        username = username.strip()
        if len(username) > 64 or len(password) > 256:
            return None, "使用者名稱或密碼過長"
        if not username or not password:
            return None, "使用者名稱與密碼不可為空"
        
        if len(password) < 6:
            return None, "密碼長度至少需要 6 個字元"

        existing = User.query.filter_by(username=username).first()
        if existing:
            return None, "此使用者名稱已被註冊"

        from app.models.user import generate_user_uid
        uid = generate_user_uid()
        while User.query.filter_by(uid=uid).first():
            uid = generate_user_uid()

        user = User(username=username, uid=uid)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user, None

    @staticmethod
    def login(username, password):
        username = username.strip()
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return None, "使用者名稱或密碼錯誤"
        return user, None

    @staticmethod
    def update_gemini_key(user_id, api_key):
        user = User.query.get(user_id)
        if not user:
            return False, "找不到使用者"
        user.gemini_api_key = encrypt(api_key.strip())
        # Legacy key updates must not leave an unrelated named model active.
        from app.models.connection import ModelConnection
        ModelConnection.query.filter_by(user_id=user_id).update({"active": False})
        db.session.commit()
        return True, None
