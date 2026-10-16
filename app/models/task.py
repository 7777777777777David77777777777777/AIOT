import uuid
from datetime import datetime
from app.database import db


class ChatMetadata(db.Model):
    __tablename__ = 'chat_metadata'
    chat_id = db.Column(db.String(36), db.ForeignKey('question_batches.id'), primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    manually_named = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SolveTask(db.Model):
    __tablename__ = 'solve_tasks'
    __table_args__ = (db.UniqueConstraint('user_id', 'upload_id', name='uq_task_user_upload'),)
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    chat_id = db.Column(db.String(36), db.ForeignKey('question_batches.id'), nullable=False, index=True)
    upload_id = db.Column(db.String(64), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    photo_ids = db.Column(db.Text, nullable=False)
    first_photo_number = db.Column(db.Integer, nullable=False)
    is_first = db.Column(db.Boolean, default=False, nullable=False)
    connection_id = db.Column(db.Integer, db.ForeignKey('model_connections.id'), nullable=True)
    model = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(20), default='queued', nullable=False, index=True)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    lease_token = db.Column(db.String(36), nullable=True)
    lease_until = db.Column(db.DateTime, nullable=True, index=True)
    error = db.Column(db.Text, nullable=True)
    result_message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return dict(task_id=self.id, chat_id=self.chat_id, status=self.status,
                    photo_number=self.first_photo_number, error=self.error,
                    result_status=self.result_status(), attempts=self.attempts)

    def result_status(self):
        if not self.result_message_id:
            return None
        from app.models.question import Message
        from app.answers import stored_answer
        message = db.session.get(Message, self.result_message_id)
        data = stored_answer(message.content) if message else None
        if not data:
            return None
        if any(q['clarity'] == 'unclear' for q in data['questions']):
            return 'needs_recapture'
        return 'needs_review' if any(q.get('answer_status') == 'needs_review' for q in data['questions']) else 'ready'
