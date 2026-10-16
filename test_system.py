import json
import unittest, tempfile, os, io
from unittest.mock import patch, Mock
from PIL import Image
from app import create_app
from app.config import Config
from app.database import db
from app.models.user import User, DeviceToken
from app.models.question import QuestionBatch
from app.credentials import decrypt

class SystemTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        class TestConfig(Config):
            ENCRYPT_STORED_KEYS=True
            TESTING=True
            SQLALCHEMY_DATABASE_URI='sqlite://'
            UPLOAD_FOLDER=self.temp.name
        self.app=create_app(TestConfig)
        self.a=self.app.test_client();self.b=self.app.test_client()
        for client,name in [(self.a,'alice'),(self.b,'bob')]:
            self.assertEqual(client.post('/api/auth/register',json={'username':name,'password':'test12345'}).status_code,200)
        self.a.post('/api/auth/apikey',json={'api_key':'test-key'})
    def tearDown(self):
        with self.app.app_context():db.session.remove();db.drop_all()
        self.temp.cleanup()
    def photo(self):
        b=io.BytesIO();Image.new('RGB',(20,20),'white').save(b,'JPEG');b.seek(0);return b
    def test_isolation_and_token(self):
        # Use Config upload path because photo controller uses it.
        with patch('app.controllers.photo_controller.Config.UPLOAD_FOLDER',self.temp.name):
            r=self.a.post('/api/upload',data={'photo':(self.photo(),'test.jpg')})
        self.assertEqual(r.status_code,200);d=r.json
        self.assertEqual(self.b.get('/api/tasks/'+d['batch_id']+'/status').status_code,404)
        self.assertEqual(self.b.get('/api/uploads/'+d['filename']).status_code,404)
        self.assertEqual(self.b.post('/api/solve',data={'batch_id':d['batch_id']}).status_code,404)
        self.assertEqual(len(self.b.get('/api/history').json['batches']),0)
        guest=self.app.test_client()
        self.assertEqual(guest.get('/api/history').status_code,401)
        self.assertEqual(guest.post('/api/device/token',json={}).status_code,401)
        token=self.a.post('/api/device/token',json={}).json['device']['token']
        self.assertEqual(self.a.get('/api/auth/me').json['devices'],[])
        self.assertEqual(guest.get('/api/history',headers={'Authorization':'Bearer '+token}).status_code,200)
        uid=self.a.get('/api/auth/me').json['user']['uid']
        self.assertEqual(guest.get('/api/history',headers={'Authorization':'Bearer '+uid}).status_code,200)
        with self.app.app_context():
            user=User.query.filter_by(username='alice').first()
            self.assertTrue(user.gemini_api_key.startswith('enc:'))
            self.assertEqual(decrypt(user.gemini_api_key),'test-key')
        self.assertEqual(token,uid)
        self.assertEqual(self.a.post('/api/device/token',json={}).json['device']['token'],uid)
        self.assertEqual(len(uid),6)
        self.assertNotEqual(uid,self.b.get('/api/auth/me').json['user']['uid'])
        self.assertEqual(len(guest.get('/api/history',headers={'Authorization':'Bearer '+uid.lower()}).json['batches']),1)

    def test_device_guess_limit(self):
        guest=self.app.test_client()
        for _ in range(10):
            self.assertEqual(guest.get('/api/history',headers={'Authorization':'Bearer INVALID'}).status_code,401)
        self.assertEqual(guest.get('/api/history',headers={'Authorization':'Bearer INVALID'}).status_code,429)
    def test_upload_and_origin(self):
        self.assertEqual(self.a.post('/api/upload',data={'photo':(io.BytesIO(b'fake'),'fake.jpg')}).status_code,400)
        self.assertEqual(self.a.post('/api/auth/logout',headers={'Origin':'https://evil.invalid'}).status_code,403)
        self.assertEqual(self.a.get('/admin/db').status_code,404)
    def test_photo_only_contract(self):
        self.assertEqual(self.a.post('/api/solve', data={'prompt': '只傳文字'}).status_code, 400)
        self.assertEqual(self.a.post('/api/solve', data={}).status_code, 400)

    def test_solve_and_failure(self):
        reply=Mock(status_code=200);reply.json.return_value={'candidates':[{'content':{'parts':[{'text':json.dumps({'questions':[{'number':'第 1 題','question':'二次方程式','clarity':'clear','photo_indices':[1],'solution':'因式分解得 $x=2$。','answer':'2','unclear_reason':'','recapture_hint':''}]}, ensure_ascii=False)}]}}]}
        with patch('app.controllers.photo_controller.Config.UPLOAD_FOLDER',self.temp.name),patch('app.controllers.solver_controller.requests.post',return_value=reply):
            r=self.a.post('/api/solve',data={'images[]':(self.photo(),'q.jpg')})
        self.assertEqual(r.status_code,200);bid=r.json['batch_id']
        self.assertEqual(self.a.get('/api/tasks/'+bid+'/status').json['prompt'],'第 1 題 · 二次方程式')
        with patch('app.controllers.solver_controller.requests.post',side_effect=TimeoutError('private secret')):
            r=self.a.post('/api/solve',data={'batch_id':bid,'images[]':(self.photo(),'supplement.jpg')})
        self.assertEqual(r.status_code,502);self.assertNotIn('private secret',r.json['error'])
        self.assertEqual(self.a.get('/api/tasks/'+bid+'/status').json['status'],'failed')

if __name__=='__main__':unittest.main()

