import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image
from flask import current_app
from sqlalchemy import update, exists, and_, case
from sqlalchemy.exc import IntegrityError
from app.database import db
from app.models.user import User
from app.models.question import QuestionBatch, Photo, Message
from app.models.connection import ModelConnection
from app.models.task import ChatMetadata, SolveTask
from app.controllers.photo_controller import PhotoController
from app.controllers.solver_controller import SolverController
from app.credentials import decrypt


def default_title(created=None):
    date = (created or datetime.utcnow()).replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).date()
    return f'{date.isoformat()} 未分類'


def chat_title(batch):
    meta = db.session.get(ChatMetadata, batch.id)
    return meta.title if meta else (batch.prompt or default_title(batch.created_at))


def enqueue(user_id, upload_id, chat_id, files):
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', upload_id or ''):
        raise ValueError('upload_id 必須為 8 至 64 碼英數字、連字號或底線')
    if not 1 <= len(files) <= 8:
        raise ValueError('每次需上傳 1 至 8 張照片')
    fingerprint = hashlib.sha256()
    total = 0
    for file in files:
        file.stream.seek(0, 2)
        size = file.stream.tell()
        file.stream.seek(0)
        total += size
        if size > 20 * 1024 * 1024 or total > 120 * 1024 * 1024:
            raise ValueError('每張最多 20 MB，合計最多 120 MB')
        digest = hashlib.sha256()
        while True:
            chunk = file.stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        fingerprint.update(digest.digest())
        file.stream.seek(0)
    fingerprint = fingerprint.hexdigest()
    existing = SolveTask.query.filter_by(user_id=user_id, upload_id=upload_id).first()
    if existing:
        if existing.fingerprint != fingerprint or (chat_id and existing.chat_id != chat_id):
            raise ValueError('同一 upload_id 不可用於不同照片或考試')
        return existing, True
    user = db.session.get(User, user_id)
    connection = ModelConnection.query.filter_by(user_id=user_id, active=True).first()
    if not decrypt(connection.api_key if connection else user.gemini_api_key):
        raise ValueError('請先在網站設定 Gemini API Key')
    paths = []
    try:
        if chat_id:
            batch = QuestionBatch.query.filter_by(id=chat_id, user_id=user_id).with_for_update().first()
            if not batch:
                raise LookupError('找不到此考試')
        else:
            batch = QuestionBatch(id=str(uuid.uuid4()), user_id=user_id, status='queued', prompt=default_title())
            db.session.add(batch)
            db.session.flush()
        # Serialize concurrent append operations even on SQLite.
        db.session.execute(update(QuestionBatch).where(QuestionBatch.id == batch.id).values(user_id=user_id))
        previous_count = Photo.query.filter_by(batch_id=batch.id).count()
        meta = db.session.get(ChatMetadata, batch.id)
        if not meta:
            meta = ChatMetadata(chat_id=batch.id, title=batch.prompt or default_title(batch.created_at))
            db.session.add(meta)
        meta.updated_at = datetime.utcnow()
        if batch.status != 'solving':
            batch.status = 'queued'
        photos = []
        for file in files:
            photo = PhotoController.save_photo(file, batch.id, commit=False)
            photos.append(photo.id)
            paths.append(photo.file_path)
        task = SolveTask(user_id=user_id, chat_id=batch.id, upload_id=upload_id, fingerprint=fingerprint,
                         photo_ids=json.dumps(photos), first_photo_number=previous_count+1,
                         is_first=previous_count == 0, connection_id=connection.id if connection else None,
                         model=connection.model if connection else current_app.config['DEFAULT_MODEL'])
        db.session.add(task)
        db.session.commit()
        return task, False
    except Exception as error:
        db.session.rollback()
        for path in paths:
            Path(path).unlink(missing_ok=True)
        if isinstance(error, IntegrityError):
            existing = SolveTask.query.filter_by(user_id=user_id, upload_id=upload_id).first()
            if existing and existing.fingerprint == fingerprint and (not chat_id or existing.chat_id == chat_id):
                return existing, True
        raise


def recover_expired(now=None):
    now = now or datetime.utcnow()
    affected = {t.chat_id for t in SolveTask.query.filter(SolveTask.status == 'running', SolveTask.lease_until < now)}
    if not affected:
        db.session.rollback()
        return
    db.session.execute(update(SolveTask).where(SolveTask.status == 'running', SolveTask.lease_until < now)
                       .values(status=case((SolveTask.attempts < 3, 'queued'), else_='failed'),
                               error=case((SolveTask.attempts < 3, None), else_='工作多次中斷，請重新上傳'),
                               lease_token=None, lease_until=None).execution_options(synchronize_session=False))
    for chat_id in affected:
        batch = db.session.get(QuestionBatch, chat_id)
        if SolveTask.query.filter_by(chat_id=chat_id, status='running').first():
            batch.status = 'solving'
        elif SolveTask.query.filter_by(chat_id=chat_id, status='queued').first():
            batch.status = 'queued'
        else:
            batch.status = 'failed'
    db.session.commit()


def claim_one():
    recover_expired()
    candidates = [t.id for t in SolveTask.query.filter_by(status='queued').order_by(SolveTask.created_at, SolveTask.id).limit(30)]
    db.session.rollback()
    for task_id in candidates:
        task = db.session.get(SolveTask, task_id)
        if not task:
            continue
        batch = QuestionBatch.query.filter_by(id=task.chat_id).with_for_update(skip_locked=True).first()
        if not batch:
            db.session.rollback()
            continue
        token = str(uuid.uuid4())
        # Atomic predicate prevents two SQLite workers claiming the same chat.
        running = exists().where(and_(SolveTask.chat_id == task.chat_id, SolveTask.status == 'running'))
        changed = db.session.execute(update(SolveTask).where(SolveTask.id == task.id, SolveTask.status == 'queued', ~running)
                                     .values(status='running', lease_token=token,
                                             lease_until=datetime.utcnow()+timedelta(minutes=10),
                                             attempts=SolveTask.attempts+1).execution_options(synchronize_session=False)).rowcount
        if not changed:
            db.session.rollback()
            continue
        batch.status = 'solving'
        db.session.commit()
        return task_id, token
    return None


def run_one():
    claimed = claim_one()
    if not claimed:
        return False
    task_id, token = claimed
    try:
        task = db.session.get(SolveTask, task_id)
        batch = QuestionBatch.query.filter_by(id=task.chat_id).with_for_update().first()
        user = db.session.get(User, task.user_id)
        connection = db.session.get(ModelConnection, task.connection_id) if task.connection_id else None
        key = decrypt(connection.api_key if connection else user.gemini_api_key)
        photos = [db.session.get(Photo, pid) for pid in json.loads(task.photo_ids)]
        if not key or any(not p or not Path(p.file_path).is_file() for p in photos):
            raise ValueError('照片或模型設定已不存在，請重新上傳或設定金鑰')
        history = [{'role': m.role, 'content': m.content} for m in batch.messages[-6:]]
        model = task.model
        batch_id = batch.id
        db.session.rollback()  # Do not hold database locks during the network call.
        result = SolverController.process_solution(batch_id, '請依本次照片題號解題，歷史內容僅供參考。', photos, key,
                                                    model_name=model, history_messages=history, persist=False)
        db.session.rollback()
        # Lock and recheck the lease before publishing one atomic result.
        task = SolveTask.query.filter_by(id=task_id).with_for_update().first()
        if task.status != 'running' or task.lease_token != token:
            db.session.rollback()
            return True
        payload = dict(format='answer_sheet_v1', questions=result['questions'], chat_metadata=result.get('chat_metadata', {}))
        message = Message(batch_id=task.chat_id, role='model', content=json.dumps(payload, ensure_ascii=False))
        db.session.add(Message(batch_id=task.chat_id, role='user', content='照片上傳 · ' + task.upload_id))
        db.session.add(message)
        db.session.flush()
        task.result_message_id = message.id
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.lease_until = None
        batch = QuestionBatch.query.filter_by(id=task.chat_id).with_for_update().first()
        meta = db.session.get(ChatMetadata, task.chat_id)
        if task.is_first and not meta.manually_named:
            naming = result.get('chat_metadata') or {}
            meta.title = naming.get('exam_title', '').strip()[:100] or (default_title(batch.created_at).replace('未分類', naming.get('subject', '').strip()[:60] or '未分類'))
        batch.prompt = meta.title
        batch.status = result.get('status', 'ready')
        db.session.commit()
    except Exception:
        db.session.rollback()
        task = db.session.get(SolveTask, task_id)
        if task and task.lease_token == token and task.status == 'running':
            task.status = 'failed'
            task.error = '解題失敗，請檢查照片是否仍存在、模型設定或網路後重試'
            task.completed_at = datetime.utcnow()
            task.lease_until = None
            db.session.get(QuestionBatch, task.chat_id).status = 'failed'
            db.session.commit()
    return True
