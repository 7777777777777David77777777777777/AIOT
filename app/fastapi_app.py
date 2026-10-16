"""Native device/task API with an explicit legacy compatibility mount."""
import hashlib
import json
import re
from collections import OrderedDict
from threading import Lock
from time import monotonic
from typing import Optional
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from werkzeug.datastructures import FileStorage
from itsdangerous import BadSignature
from sqlalchemy import func
from app import create_app
from app.database import db
from app.models.user import User
from app.models.question import QuestionBatch, Message
from app.models.task import ChatMetadata, SolveTask
from app.controllers.device_controller import DeviceController
from app.answers import stored_answer
from app.task_service import enqueue, chat_title


class RenameChat(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class TooLarge(Exception):
    pass


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            length = 0
        if length > 128 * 1024 * 1024:
            return await JSONResponse({'error': '照片合計最多 120 MB'}, status_code=413)(scope, receive, send)
        size = 0
        async def limited_receive():
            nonlocal size
            message = await receive()
            size += len(message.get('body', b''))
            if size > 128 * 1024 * 1024:
                raise TooLarge()
            return message
        try:
            await self.app(scope, limited_receive, send)
        except TooLarge:
            await JSONResponse({'error': '照片合計最多 120 MB'}, status_code=413)(scope, receive, send)


def plain_text(text):
    text = text or ''
    for _ in range(4):
        text = re.sub(r'\\(?:dfrac|tfrac|frac)\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', text)
    text = re.sub(r'\\(?:mathrm|text|mathbf)\{([^{}]*)\}', r'\1', text)
    for key, value in {'times': '×', 'cdot': '·', 'approx': '≈', 'leq': '≤', 'geq': '≥', 'pi': 'π', 'mu': 'μ', 'sqrt': '√'}.items():
        text = re.sub(r'\\' + key + r'\b', lambda m: value, text)
    text = re.sub(r'\\[()\[\]]|\$|\*\*', '', text)
    return re.sub(r'<[^>]*>', '', text).strip()


def create_fastapi(legacy=None):
    legacy = legacy or create_app()
    api = FastAPI(title='AIOT Photo Exam API', version='1.0.0', docs_url='/api/docs', openapi_url='/api/openapi.json', redoc_url='/api/redoc')
    api.state.legacy = legacy
    failures, lock = OrderedDict(), Lock()
    security = HTTPBearer(auto_error=False)

    @api.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({'error': str(error)}, status_code=400)

    @api.exception_handler(LookupError)
    async def missing(request, error):
        return JSONResponse({'error': str(error)}, status_code=404)

    @api.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse({'error': error.detail}, status_code=error.status_code, headers=error.headers)

    @api.middleware('http')
    async def headers_and_origin(request: Request, call_next):
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('origin')
            if origin and origin != str(request.base_url).rstrip('/'):
                return JSONResponse({'error': '不接受跨網站操作'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    def identity(request: Request, credentials=Depends(security)):
        with legacy.app_context():
            if credentials:
                address = request.client.host if request.client else 'unknown'
                now = monotonic()
                with lock:
                    attempts = [t for t in failures.get(address, []) if now-t < 60]
                    if len(attempts) >= 10:
                        raise HTTPException(429, '裝置碼錯誤次數過多，請 60 秒後再試', headers={'Retry-After': '60'})
                    device = DeviceController.verify_token(credentials.credentials)
                    if not device:
                        failures[address] = attempts + [now]
                        failures.move_to_end(address)
                        if len(failures) > 10000:
                            failures.popitem(last=False)
                        raise HTTPException(401, '裝置碼無效')
                    return device.user_id
            cookie = request.cookies.get(legacy.config.get('SESSION_COOKIE_NAME', 'session'))
            if cookie:
                try:
                    data = legacy.session_interface.get_signing_serializer(legacy).loads(cookie, max_age=int(legacy.permanent_session_lifetime.total_seconds()))
                    uid = data.get('user_id')
                    if type(uid) is int and db.session.get(User, uid):
                        return uid
                except BadSignature:
                    pass
            raise HTTPException(401, '請登入或提供 UID')

    @api.get('/api/v1/health')
    def health():
        from sqlalchemy import text
        with legacy.app_context():
            db.session.execute(text('SELECT 1'))
        return {'ok': True, 'api': 'fastapi'}

    @api.get('/api/v1/chats')
    def chats(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=20), user_id: int = Depends(identity)):
        with legacy.app_context():
            query = QuestionBatch.query.filter_by(user_id=user_id).outerjoin(ChatMetadata, ChatMetadata.chat_id == QuestionBatch.id)
            total = query.count()
            rows = query.order_by(func.coalesce(ChatMetadata.updated_at, QuestionBatch.created_at).desc(), QuestionBatch.id).offset((page-1)*limit).limit(limit).all()
            return dict(username=db.session.get(User, user_id).username,
                        chats=[dict(id=b.id, title=chat_title(b), status=b.status) for b in rows],
                        page=page, has_more=page*limit < total)

    @api.post('/api/v1/uploads', status_code=202, openapi_extra={
        'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
            'type': 'object', 'required': ['upload_id'], 'properties': {
                'upload_id': {'type': 'string', 'description': '拍攝時產生並在重試時沿用，8 至 64 字元'},
                'chat_id': {'type': 'string', 'description': '新考試省略，追加照片填原 ID'},
                'photo': {'type': 'string', 'format': 'binary', 'description': 'ESP32 單張照片'},
                'images': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'}, 'description': '網頁多張照片；每次最多 8 張'}
            }}}}}
    })
    async def upload(request: Request, user_id: int = Depends(identity)):
        form = await request.form(max_files=16, max_fields=16)
        files = [item for name, item in form.multi_items() if name in {'photo', 'image', 'images', 'images[]'} and hasattr(item, 'file')]
        storages = [FileStorage(stream=f.file, filename=f.filename, content_type=f.content_type) for f in files]
        upload_id, chat_id = str(form.get('upload_id', '')), str(form.get('chat_id') or '') or None
        def queue():
            with legacy.app_context():
                task, replay = enqueue(user_id, upload_id, chat_id, storages)
                return dict(**task.to_dict(), replayed=replay)
        try:
            result = await run_in_threadpool(queue)
            return JSONResponse(result, status_code=200 if result['replayed'] else 202)
        finally:
            await form.close()

    @api.get('/api/v1/tasks/{task_id}')
    def task_status(task_id: str, user_id: int = Depends(identity)):
        with legacy.app_context():
            task = SolveTask.query.filter_by(id=task_id, user_id=user_id).first()
            if not task:
                raise HTTPException(404, '找不到此工作')
            return task.to_dict()

    @api.post('/api/v1/tasks/{task_id}/retry', status_code=202)
    def retry(task_id: str, user_id: int = Depends(identity)):
        from app.models.connection import ModelConnection
        with legacy.app_context():
            task = SolveTask.query.filter_by(id=task_id, user_id=user_id).with_for_update().first()
            if not task:
                raise HTTPException(404, '找不到此工作')
            if task.status != 'failed' or task.attempts >= 3:
                raise HTTPException(409, '工作無法重試，請重新拍攝上傳')
            connection = ModelConnection.query.filter_by(user_id=user_id, active=True).first()
            task.connection_id = connection.id if connection else None
            task.model = connection.model if connection else legacy.config['DEFAULT_MODEL']
            task.status, task.error, task.lease_token, task.lease_until = 'queued', None, None, None
            db.session.commit()
            return task.to_dict()

    @api.post('/api/v1/chats/{chat_id}/title')
    def rename(chat_id: str, data: RenameChat, user_id: int = Depends(identity)):
        with legacy.app_context():
            batch = QuestionBatch.query.filter_by(id=chat_id, user_id=user_id).with_for_update().first()
            if not batch:
                raise HTTPException(404, '找不到此考試')
            title = data.title.strip()
            if not title:
                raise ValueError('名稱不可空白')
            meta = db.session.get(ChatMetadata, chat_id)
            if not meta:
                meta = ChatMetadata(chat_id=chat_id, title=title)
                db.session.add(meta)
            meta.title, meta.manually_named, batch.prompt = title, True, title
            db.session.commit()
            return dict(chat_id=chat_id, title=title)

    @api.get('/api/v1/chats/{chat_id}/records')
    def records(chat_id: str, cursor: str = '0:0', limit: int = Query(10, ge=1, le=20),
                task_id: Optional[str] = None, format: str = Query('device', pattern='^(device|web)$'),
                user_id: int = Depends(identity)):
        try:
            start, index = map(int, cursor.split(':'))
            if start < 0 or index < 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(400, '無效的分頁游標')
        with legacy.app_context():
            batch = QuestionBatch.query.filter_by(id=chat_id, user_id=user_id).first()
            if not batch:
                raise HTTPException(404, '找不到此考試')
            query = Message.query.filter_by(batch_id=chat_id, role='model').filter(Message.id >= start)
            if task_id:
                task = SolveTask.query.filter_by(id=task_id, chat_id=chat_id, user_id=user_id).first()
                if not task:
                    raise HTTPException(404, '找不到此工作')
                if task.status != 'completed':
                    raise HTTPException(409, '工作尚未完成')
                query = query.filter(Message.id == task.result_message_id)
            items, next_cursor = [], None
            for message in query.order_by(Message.id).limit(21):
                parsed = stored_answer(message.content)
                questions = parsed['questions'] if parsed else [dict(number='未標示', photo_indices=[], clarity='unclear', confidence=None, answer='', solution=message.content, answer_status='needs_review', review_note='舊版紀錄尚未結構化')]
                for position, q in enumerate(questions):
                    if message.id == start and position < index:
                        continue
                    if len(items) == limit:
                        next_cursor = f'{message.id}:{position}'
                        break
                    if format == 'web':
                        item = dict(q)
                    else:
                        answer = q.get('answer') or ('無法作答：照片不清楚' if q['clarity'] == 'unclear' else '待確認')
                        item = {key: q.get(key) for key in ('number', 'photo_indices', 'clarity', 'confidence', 'answer_status', 'review_note')}
                        item.update(answer=plain_text(answer), solution=plain_text(q.get('solution')))
                    items.append(item)
                if next_cursor:
                    break
            return dict(chat_id=chat_id, title=chat_title(batch), items=items, has_more=next_cursor is not None, next_cursor=next_cursor)

    api.add_middleware(BodyLimit)
    # Explicit transitional compatibility; device/task routes above are native FastAPI.
    api.mount('/', WSGIMiddleware(legacy))
    return api
