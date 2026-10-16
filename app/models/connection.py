from datetime import datetime
from app.database import db


class ModelConnection(db.Model):
    __tablename__ = "model_connections"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    api_key = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(128), nullable=False)
    active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return dict(id=self.id, name=self.name, model=self.model, active=self.active,
                    created_at=self.created_at.isoformat())
