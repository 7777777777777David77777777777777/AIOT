import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from PIL import Image
from fastapi.testclient import TestClient
from app import create_app
from app.config import Config
from app.fastapi_app import create_fastapi
from app.database import db
from app.models.user import User
from app.models.question import Message, Photo, QuestionBatch
from app.models.task import SolveTask, ChatMetadata
from app.task_service import run_one, claim_one, recover_expired


class FastAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        class TestConfig(Config):
            TESTING=True
            SQLALCHEMY_DATABASE_URI='sqlite:///' + self.tmp.name.replace('\\','/') + '/test.db'
            UPLOAD_FOLDER=self.tmp.name
        self.legacy=create_app(TestConfig)
        self.api=create_fastapi(self.legacy)
        self.a=TestClient(self.api);self.b=TestClient(self.api)
        for client,name in [(self.a,'alice-fast'),(self.b,'bob-fast')]:
            response=client.post('/api/auth/register',json={'username':name,'password':'TestPassword123!'})
            self.assertEqual(response.status_code,200)
            client.post('/api/auth/apikey',json={'api_key':'fixture-key'})
        self.code=self.a.get('/api/auth/me').json()['user']['uid']
        self.device=TestClient(self.api,headers={'Authorization':'Bearer '+self.code})

    def tearDown(self):
        for client in [self.a,self.b,self.device]:client.close()
        with self.legacy.app_context():db.session.remove();db.engine.dispose()
        self.tmp.cleanup()

    def image(self):
        stream=io.BytesIO();Image.new('RGB',(30,30),'white').save(stream,'PNG');return stream.getvalue()

    def upload(self, client=None, upload_id='upload-0001', chat_id=None, data=None):
        fields={'upload_id':upload_id}
        if chat_id:fields['chat_id']=chat_id
        return (client or self.device).post('/api/v1/uploads',data=fields,files={'photo':('q.png',data or self.image(),'image/png')})

    def reply(self, metadata=None, unclear=False):
        q=dict(number='1',question='求值',clarity='unclear' if unclear else 'clear',photo_indices=[1],solution='' if unclear else '代入得 2',answer='' if unclear else '2',confidence=25 if unclear else 90,unclear_reason='裁切' if unclear else '',recapture_hint='補拍右側' if unclear else '')
        response=Mock(status_code=200)
        response.json.return_value={'candidates':[{'content':{'parts':[{'text':json.dumps({'questions':[q],'chat_metadata':metadata or {'exam_title':'電工原理第一次段考','subject':'電工原理'}})}]}}]}
        return response

    def work(self, reply=None):
        with self.legacy.app_context(),patch('app.controllers.solver_controller.requests.post',return_value=reply or self.reply()) as model:
            self.assertTrue(run_one())
            return model.call_count

    def test_device_full_flow_new_append_title_and_records(self):
        self.assertEqual(self.device.get('/api/v1/chats').json()['chats'],[])
        first=self.upload();self.assertEqual(first.status_code,202,first.text)
        ids=first.json();self.assertNotEqual(ids['chat_id'],ids['task_id'])
        self.assertEqual(self.device.get('/api/v1/tasks/'+ids['task_id']).json()['status'],'queued')
        self.assertEqual(self.work(),1)
        state=self.device.get('/api/v1/tasks/'+ids['task_id']).json();self.assertEqual(state['status'],'completed')
        listing=self.device.get('/api/v1/chats').json()['chats'];self.assertEqual(listing[0]['title'],'電工原理第一次段考')
        record=self.device.get('/api/v1/chats/'+ids['chat_id']+'/records').json()
        self.assertEqual(record['items'][0]['answer'],'2');self.assertNotIn('question',record['items'][0])
        self.assertEqual(record['items'][0]['confidence'],90)
        second=self.upload(upload_id='upload-0002',chat_id=ids['chat_id']);self.assertEqual(second.status_code,202)
        self.assertEqual(second.json()['chat_id'],ids['chat_id']);self.assertEqual(second.json()['photo_number'],2)
        self.work(self.reply({'exam_title':'不應覆蓋','subject':'數學'}))
        self.assertEqual(self.device.get('/api/v1/chats').json()['chats'][0]['title'],'電工原理第一次段考')
        records=self.device.get('/api/v1/chats/'+ids['chat_id']+'/records?limit=1').json()
        self.assertTrue(records['has_more'])
        page2=self.device.get('/api/v1/chats/'+ids['chat_id']+'/records',params={'cursor':records['next_cursor']}).json()
        self.assertEqual(page2['items'][0]['photo_indices'],[2])

    def test_idempotency_and_conflict(self):
        first=self.upload().json()
        repeat=self.upload();self.assertEqual(repeat.status_code,200)
        self.assertEqual(repeat.json()['task_id'],first['task_id'])
        self.assertEqual(self.upload(data=self.image()+b'changed').status_code,400)
        with self.legacy.app_context():
            self.assertEqual(Photo.query.count(),1);self.assertEqual(SolveTask.query.count(),1);self.assertEqual(QuestionBatch.query.count(),1)
        self.work()
        repeat=self.upload();self.assertEqual(repeat.json()['status'],'completed')
        with self.legacy.app_context():self.assertFalse(run_one());self.assertEqual(Message.query.filter_by(role='model').count(),1)

    def test_ownership_and_invalid_upload_atomicity(self):
        first=self.upload().json()
        self.assertEqual(self.b.get('/api/v1/tasks/'+first['task_id']).status_code,404)
        self.assertEqual(self.b.get('/api/v1/chats/'+first['chat_id']+'/records').status_code,404)
        self.assertEqual(self.upload(self.b,chat_id=first['chat_id']).status_code,404)
        self.assertEqual(self.upload(upload_id='bad-file-01',data=b'not a picture').status_code,400)
        with self.legacy.app_context():self.assertEqual(QuestionBatch.query.count(),1)
        guest=TestClient(self.api)
        self.assertEqual(guest.get('/api/v1/chats').status_code,401);guest.close()

    def test_failed_task_retry_and_terminal_unclear(self):
        task=self.upload().json()
        with self.legacy.app_context(),patch('app.controllers.solver_controller.requests.post',side_effect=TimeoutError('private-secret')):
            run_one()
        state=self.device.get('/api/v1/tasks/'+task['task_id']).json()
        self.assertEqual(state['status'],'failed');self.assertNotIn('private-secret',str(state))
        self.assertEqual(self.device.post('/api/v1/tasks/'+task['task_id']+'/retry').status_code,202)
        self.work(self.reply(unclear=True))
        state=self.device.get('/api/v1/tasks/'+task['task_id']).json()
        self.assertEqual(state['status'],'completed');self.assertEqual(state['result_status'],'needs_recapture')
        result=self.device.get('/api/v1/chats/'+task['chat_id']+'/records').json()['items'][0]
        self.assertIn('照片不清楚',result['answer'])

    def test_recovery_and_manual_title(self):
        first=self.upload().json()
        with self.legacy.app_context():
            claim=claim_one();self.assertIsNotNone(claim)
            task=db.session.get(SolveTask,first['task_id']);task.lease_until=datetime.utcnow()-timedelta(seconds=1);db.session.commit()
            recover_expired();self.assertEqual(db.session.get(SolveTask,task.id).status,'queued')
        self.assertEqual(self.device.post('/api/v1/chats/'+first['chat_id']+'/title',json={'title':'自訂考試'}).status_code,200)
        self.work()
        self.assertEqual(self.device.get('/api/v1/chats').json()['chats'][0]['title'],'自訂考試')

    def test_schema_and_cross_origin(self):
        self.assertIn('/api/v1/tasks/{task_id}',self.a.get('/api/openapi.json').json()['paths'])
        self.assertEqual(self.a.post('/api/v1/chats/no/title',json={'title':'測試'},headers={'Origin':'https://evil.invalid'}).status_code,403)

    def test_two_queued_jobs_same_chat_serialize_and_recover_limit(self):
        first=self.upload().json()
        second=self.upload(upload_id='upload-next',chat_id=first['chat_id']).json()
        with self.legacy.app_context():
            claimed=claim_one();self.assertEqual(claimed[0],first['task_id'])
            self.assertIsNone(claim_one())
            running=db.session.get(SolveTask,first['task_id']);running.attempts=3
            running.lease_until=datetime.utcnow()-timedelta(seconds=1);db.session.commit()
            recover_expired()
            self.assertEqual(db.session.get(SolveTask,first['task_id']).status,'failed')
            claimed=claim_one();self.assertEqual(claimed[0],second['task_id'])

    def test_first_photo_subject_fallback_date_and_missing_metadata(self):
        first=self.upload().json()
        self.work(self.reply({'exam_title':'','subject':'數學'}))
        listing=self.device.get('/api/v1/chats').json()['chats']
        self.assertRegex(listing[0]['title'],r'^\d{4}-\d{2}-\d{2} 數學$')
        self.assertEqual(listing[0]['id'],first['chat_id'])

    def test_restart_reuses_task_data_and_rejects_oversize_request(self):
        first=self.upload().json()
        replacement=TestClient(create_fastapi(self.legacy),headers={'Authorization':'Bearer '+self.code})
        self.assertEqual(replacement.get('/api/v1/tasks/'+first['task_id']).json()['status'],'queued')
        self.assertEqual(replacement.post('/api/v1/uploads',headers={'Content-Length':str(129*1024*1024)}).status_code,413)
        replacement.close()

    def test_middle_invalid_photo_rolls_back_all_files_and_chat(self):
        from pathlib import Path
        result=self.device.post('/api/v1/uploads',data={'upload_id':'invalid-multi'},files=[('images',('ok.png',self.image(),'image/png')),('images',('bad.png',b'bad','image/png'))])
        self.assertEqual(result.status_code,400)
        with self.legacy.app_context():
            self.assertEqual(QuestionBatch.query.count(),0);self.assertEqual(Photo.query.count(),0);self.assertEqual(SolveTask.query.count(),0)
        self.assertEqual(list(Path(self.tmp.name).glob('*.png')),[])
