import json
"""Integration tests for real PHP pages -> Python API, without paid model calls."""
import io, os, re, socket, subprocess, tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
from PIL import Image
from werkzeug.serving import make_server
from app import create_app
from app.config import Config

ROOT=Path(__file__).resolve().parent
PHP=Path(os.environ.get('PHP_BINARY', str(ROOT/'.runtime'/'php'/'php.exe')))
def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

class PHPBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.api_port=free_port(); self.web_port=free_port()
        class TestConfig(Config):
            ENCRYPT_STORED_KEYS=True
            TESTING=True
            SQLALCHEMY_DATABASE_URI='sqlite://'
            UPLOAD_FOLDER=self.tmp.name
        self.app=create_app(TestConfig)
        self.api=make_server('127.0.0.1',self.api_port,self.app,threaded=True)
        self.thread=threading.Thread(target=self.api.serve_forever,daemon=True);self.thread.start()
        env=os.environ.copy();env['PYTHON_API_URL']='http://127.0.0.1:'+str(self.api_port)
        self.php=subprocess.Popen([str(PHP),'-d','upload_max_filesize=20M','-d','post_max_size=128M','-d','max_file_uploads=16','-d','session.save_path='+self.tmp.name,'-S','127.0.0.1:'+str(self.web_port),'-t',str(ROOT/'web'),str(ROOT/'web'/'router.php')],cwd=PHP.parent,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.base='http://127.0.0.1:'+str(self.web_port);self.client=requests.Session()
        for _ in range(100):
            try:
                r=self.client.get(self.base+'/login.php',timeout=.5)
                if r.status_code==200:break
            except requests.RequestException:time.sleep(.05)
        else:raise RuntimeError('PHP server did not start')
    def tearDown(self):
        self.client.close();self.php.terminate();self.php.wait(timeout=5);self.api.shutdown();self.api.server_close();self.tmp.cleanup()
    def test_php_admin_page_permissions(self):
        page=self.client.get(self.base+'/login.php?mode=register')
        csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',page.text).group(1)
        self.client.post(self.base+'/login.php?mode=register',data={'csrf':csrf,'username':'admin-page-test','password':'test12345','confirm_password':'test12345'})
        self.assertEqual(self.client.get(self.base+'/admin.php').status_code,403)
        from app.models.user import User
        from app.models.admin import AdminRole
        from app.database import db
        with self.app.app_context():
            user=User.query.filter_by(username='admin-page-test').first()
            db.session.add(AdminRole(user_id=user.id));db.session.commit()
        page=self.client.get(self.base+'/admin.php')
        self.assertEqual(page.status_code,200)
        self.assertIn('id="memberList"',page.text)
        self.assertEqual(self.client.get(self.base+'/api/admin/members').json()['total'],1)

    def test_php_login_multi_photo_and_csrf(self):
        page=self.client.get(self.base+'/login.php?mode=register')
        csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',page.text).group(1)
        r=self.client.post(self.base+'/login.php?mode=register',data={'csrf':csrf,'username':'php_bridge_user','password':'test12345','confirm_password':'test12345'})
        self.assertEqual(r.status_code,200,r.text[:300]);self.assertIn('/index.php',r.url)
        self.assertNotIn('A LITTLE CLARITY',r.text)
        self.assertNotIn('id="prompt"',r.text)
        self.assertIn('name="csrf-token"',r.text)
        csrf=re.search(r'name="csrf-token" content="([a-f0-9]+)"',r.text).group(1)
        headers={'X-CSRF-Token':csrf}
        self.assertTrue(self.client.get(self.base+'/api/auth/me').json()['authenticated'])
        self.assertEqual(self.client.post(self.base+'/api/auth/apikey',json={'api_key':'fixture-only'}).status_code,403)
        self.assertEqual(self.client.post(self.base+'/api/auth/apikey',headers=headers,json={'api_key':'fixture-only'}).status_code,200)
        image=io.BytesIO();Image.new('RGB',(30,30),'white').save(image,'PNG');data=image.getvalue()
        reply=Mock(status_code=200);reply.json.return_value={'candidates':[{'content':{'parts':[{'text':json.dumps({'questions':[{'number':'第 1 題','question':'二次方程式','clarity':'clear','photo_indices':[1],'solution':'因式分解得 $x=2$。','answer':'2','unclear_reason':'','recapture_hint':''}]}, ensure_ascii=False)}]}}]}
        large_data=data + b'\0' * (9 * 1024 * 1024)
        large=self.client.post(self.base+'/api/upload',headers=headers,files={'photo':('large.png',large_data,'image/png')})
        self.assertEqual(large.status_code,200,large.text[:200])
        with patch('app.controllers.solver_controller.requests.post',return_value=reply):
            response=self.client.post(self.base+'/api/solve',headers=headers,files=[('images[]',('page1.png',data,'image/png')),('images[]',('page2.png',data,'image/png'))])
        self.assertEqual(response.status_code,200,response.text)
        history=self.client.get(self.base+'/api/history').json()['batches']
        self.assertEqual(len(history[0]['photos']),2)
        self.assertIn('二次方程式',history[0]['prompt'])
        photo=history[0]['photos'][0]['filename']
        self.assertEqual(self.client.get(self.base+'/api/uploads/'+photo).content,data)
        self.assertEqual(self.client.get(self.base+'/static/vendor/katex/katex.min.js').status_code,200)
        self.assertEqual(self.client.get(self.base+'/bootstrap.php').status_code,404)
        self.assertEqual(self.client.post(self.base+'/api/auth/logout',headers=headers,json={}).status_code,200)
        self.assertFalse(self.client.get(self.base+'/api/auth/me').json()['authenticated'])
        login=self.client.get(self.base+'/login.php');csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',login.text).group(1)
        wrong=self.client.post(self.base+'/login.php',data={'csrf':csrf,'username':'php_bridge_user','password':'wrongpass'})
        self.assertIn('密碼錯誤',wrong.text)

if __name__=='__main__':unittest.main()
