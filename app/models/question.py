from app.answers import stored_answer, answer_text
from datetime import datetime
import uuid
from app.database import db

class QuestionBatch(db.Model):
    __tablename__ = "question_batches"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status = db.Column(db.String(20), default="ready") # queued, solving, rendering, ready, failed, needs_recapture
    prompt = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 關聯
    photos = db.relationship("Photo", backref="batch", cascade="all, delete-orphan", lazy=True)
    messages = db.relationship("Message", backref="batch", cascade="all, delete-orphan", lazy=True, order_by="Message.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "prompt": self.prompt,
            "photos": [p.to_dict() for p in self.photos],
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat()
        }

class Photo(db.Model):
    __tablename__ = "photos"
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = db.Column(db.String(36), db.ForeignKey("question_batches.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    mime_type = db.Column(db.String(50), default="image/jpeg")
    file_size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "created_at": self.created_at.isoformat()
        }

class Message(db.Model):
    __tablename__ = "messages"
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(36), db.ForeignKey("question_batches.id"), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # user 或 model
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": answer_text(stored_answer(self.content)) if self.role == "model" and stored_answer(self.content) else self.content,
            "questions": (stored_answer(self.content) or {}).get("questions") if self.role == "model" else None,
            "created_at": self.created_at.isoformat()
        }
