import os
import tempfile
import unittest
from unittest.mock import patch
from app import create_app
from app.config import Config
from app.database import db


class RenderProxyTests(unittest.TestCase):
    def test_https_origin_and_secure_session(self):
        with tempfile.TemporaryDirectory() as folder:
            class TestConfig(Config):
                TESTING = True
                SQLALCHEMY_DATABASE_URI = 'sqlite://'
                UPLOAD_FOLDER = folder
                SESSION_COOKIE_SECURE = True
            with patch.dict(os.environ, {'TRUST_PROXY': '1'}):
                app = create_app(TestConfig)
            client = app.test_client()
            headers = {'Host': 'photo-test.onrender.com', 'X-Forwarded-Proto': 'https',
                       'Origin': 'https://photo-test.onrender.com'}
            response = client.post('/api/auth/register', headers=headers,
                                   json={'username': 'render-test', 'password': 'TestPassword123!'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('Secure;', response.headers['Set-Cookie'])
            self.assertEqual(client.get('/api/health').json, {'ok': True})
            headers['Origin'] = 'https://wrong.example'
            self.assertEqual(client.post('/api/auth/logout', headers=headers).status_code, 403)
            with app.app_context():
                db.session.remove()
                db.drop_all()
