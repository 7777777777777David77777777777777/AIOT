from flask import Blueprint, request, jsonify, session, abort
from app.database import db
from app.models.user import User
from app.models.question import QuestionBatch, Photo
from app.models.connection import ModelConnection
from app.models.admin import is_admin, AdminAudit
from app.credentials import decrypt

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.before_request
def require_admin():
    if not session.get('user_id'):
        return jsonify(error='請先登入管理員帳號'), 401
    if not is_admin(session['user_id']):
        return jsonify(error='只有管理員可以查看'), 403


def page_number():
    return max(1, request.args.get('page', 1, type=int) or 1)


@admin_bp.route('/members')
def members():
    query = User.query
    search = request.args.get('q', '').strip()[:64]
    if search:
        query = query.filter(User.username.contains(search, autoescape=True))
    page = page_number()
    total = query.count()
    result = []
    for user in query.order_by(User.id.desc()).offset((page - 1) * 20).limit(20):
        record = user.to_dict()
        record['batch_count'] = QuestionBatch.query.filter_by(user_id=user.id).count()
        active = ModelConnection.query.filter_by(user_id=user.id, active=True).first()
        record['active_model'] = active.model if active else None
        result.append(record)
    return jsonify(members=result, total=total, page=page, pages=max(1, (total+19)//20))


@admin_bp.route('/members/<int:user_id>')
def detail(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    page = page_number()
    query = QuestionBatch.query.filter_by(user_id=user_id)
    total = query.count()
    return jsonify(user=user.to_dict(), connections=[c.to_dict() for c in ModelConnection.query.filter_by(user_id=user_id).order_by(ModelConnection.created_at.desc())],
                   batches=[b.to_dict() for b in query.order_by(QuestionBatch.created_at.desc()).offset((page-1)*10).limit(10)],
                   page=page, pages=max(1, (total+9)//10), total=total)


@admin_bp.route('/members/<int:user_id>/keys', methods=['POST'])
def reveal_keys(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    db.session.add(AdminAudit(admin_id=session['user_id'], target_id=user_id, action='view_api_keys'))
    db.session.commit()
    return jsonify(current_key=decrypt(user.gemini_api_key), connections=[dict(id=c.id, name=c.name, model=c.model, api_key=decrypt(c.api_key)) for c in ModelConnection.query.filter_by(user_id=user_id)])
