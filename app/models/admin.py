from datetime import datetime
from app.database import db


class AdminRole(db.Model):
    __tablename__ = 'admin_roles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)


class AdminAudit(db.Model):
    __tablename__ = 'admin_audit'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def is_admin(user_id):
    from flask import current_app
    from app.models.user import User
    user = db.session.get(User, user_id) if user_id else None
    allowed = {s.strip().upper() for s in current_app.config.get('ADMIN_UIDS', '').split(',') if s.strip()}
    return bool(user and (db.session.get(AdminRole, user.id) or user.uid in allowed))
