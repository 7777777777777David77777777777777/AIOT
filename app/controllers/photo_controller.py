import os
import uuid
from flask import current_app
from PIL import Image
from io import BytesIO
from werkzeug.utils import secure_filename
from app.config import Config
from app.models.question import Photo
from app.database import db

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

class PhotoController:
    @staticmethod
    def is_allowed_file(filename):
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    @staticmethod
    def save_photo(file_storage, batch_id):
        """
        儲存上傳的檔案至磁碟並寫入 Photo 資料表記錄
        """
        if not file_storage or not file_storage.filename:
            return None

        if not PhotoController.is_allowed_file(file_storage.filename):
            raise ValueError("僅接受 JPG、PNG、WebP 圖片")
        data = file_storage.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise ValueError("單張圖片不可超過 8 MB")
        try:
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > 25000000:
                    raise ValueError("圖片解析度過大")
                image.verify()
        except Exception:
            raise ValueError("圖片內容無效或解析度過大")
        file_storage.stream.seek(0)
        filename = secure_filename(file_storage.filename)
        ext = filename.rsplit(".", 1)[1].lower() if "." in filename else "jpg"
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
        
        file_storage.save(save_path)
        file_size = os.path.getsize(save_path)

        photo = Photo(
            batch_id=batch_id,
            filename=unique_name,
            file_path=save_path,
            mime_type=file_storage.mimetype or f"image/{ext}",
            file_size=file_size
        )
        db.session.add(photo)
        db.session.commit()
        return photo
