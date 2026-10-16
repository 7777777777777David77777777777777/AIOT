import io
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import json
import requests
import uvicorn
from PIL import Image
from app import create_app
from app.config import Config
from app.fastapi_app import create_fastapi
from app.task_service import run_one
from app.database import db


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));return s.getsockname()[1]


class FastAPIPHPBridgeTests(unittest.TestCase):
    def test_real_php_asgi_worker_flow(self):
        root=Path(__file__).resolve().parent
        php=Path(os.environ.get('PHP_BINARY',root/'.runtime/php/php.exe'))
        if not php.is_file():self.skipTest('PHP_BINARY required')
        with tempfile.TemporaryDirectory() as tmp:
            class TestConfig(Config):
                TESTING=True
                SQLALCHEMY_DATABASE_URI='sqlite:///'+tmp.replace('\\','/')+'/test.db'
                UPLOAD_FOLDER=tmp
            legacy=create_app(TestConfig)
            port,web=free_port(),free_port()
            server=uvicorn.Server(uvicorn.Config(create_fastapi(legacy),host='127.0.0.1',port=port,log_level='error'))
            thread=threading.Thread(target=server.run,daemon=True);thread.start()
            env=os.environ.copy();env['PYTHON_API_URL']=f'http://127.0.0.1:{port}'
            process=subprocess.Popen([str(php),'-d','session.save_path='+tmp,'-S',f'127.0.0.1:{web}','-t',str(root/'web'),str(root/'web/router.php')],cwd=php.parent,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            client=requests.Session();base=f'http://127.0.0.1:{web}'
            try:
                for _ in range(100):
                    try:
                        page=client.get(base+'/login.php?mode=register',timeout=.3)
                        if page.status_code==200 and server.started:break
                    except requests.RequestException:pass
                    time.sleep(.05)
                else:self.fail('servers failed to start')
                csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',page.text).group(1)
                page=client.post(base+'/login.php?mode=register',data={'csrf':csrf,'username':'asgi-php-test','password':'TestPassword123!','confirm_password':'TestPassword123!'})
                self.assertEqual(page.status_code,200)
                csrf=re.search(r'name="csrf-token" content="([a-f0-9]+)"',page.text).group(1)
                headers={'X-CSRF-Token':csrf}
                self.assertEqual(client.post(base+'/api/auth/apikey',headers=headers,json={'api_key':'fixture-only'}).status_code,200)
                photo=io.BytesIO();Image.new('RGB',(30,30),'white').save(photo,'PNG')
                result=client.post(base+'/api/v1/uploads',headers=headers,data={'upload_id':'php-asgi-01'},files={'images[]':('q.png',photo.getvalue(),'image/png')})
                self.assertEqual(result.status_code,202,result.text)
                ids=result.json()
                q=dict(number='1',question='求值',clarity='clear',photo_indices=[1],solution='代入得 2',answer='2',confidence=90,unclear_reason='',recapture_hint='')
                reply=Mock(status_code=200);reply.json.return_value={'candidates':[{'content':{'parts':[{'text':json.dumps({'questions':[q],'chat_metadata':{'exam_title':'整合測試考試','subject':'數學'}})}]}}]}
                with legacy.app_context(),patch('app.controllers.solver_controller.requests.post',return_value=reply):self.assertTrue(run_one())
                status=client.get(base+'/api/v1/tasks/'+ids['task_id']).json();self.assertEqual(status['status'],'completed')
                records=client.get(base+'/api/v1/chats/'+ids['chat_id']+'/records').json()
                self.assertEqual(records['title'],'整合測試考試');self.assertEqual(records['items'][0]['answer'],'2')
                self.assertEqual(client.get(base+'/api/history').json()['batches'][0]['prompt'],'整合測試考試')
            finally:
                client.close();process.terminate();process.wait(timeout=5)
                server.should_exit=True;thread.join(timeout=5)
                with legacy.app_context():db.session.remove();db.engine.dispose()
