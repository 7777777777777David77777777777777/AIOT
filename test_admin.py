from unittest.mock import patch
from test_system import SystemTests
from app.database import db
from app.models.user import User
from app.models.admin import AdminRole, AdminAudit
from app.models.question import QuestionBatch


class AdminTests(SystemTests):
    def test_permissions_member_details_and_key_audit(self):
        self.assertEqual(self.a.get('/api/admin/members').status_code,403)
        self.assertEqual(self.app.test_client().get('/api/admin/members').status_code,401)
        with self.app.app_context():
            admin = User.query.filter_by(username='alice').first()
            bob = User.query.filter_by(username='bob').first()
            aid, bid = admin.id, bob.id
            db.session.add(AdminRole(user_id=aid))
            db.session.add(QuestionBatch(user_id=bid,prompt='會員測試紀錄'))
            db.session.commit()
        self.b.post('/api/auth/apikey',json={'api_key':'member-secret'})
        self.assertTrue(self.a.get('/api/auth/me').json['user']['is_admin'])
        self.assertEqual(self.a.get('/api/admin/members?q=bob').json['total'],1)
        detail=self.a.get(f'/api/admin/members/{bid}')
        self.assertEqual(detail.status_code,200)
        self.assertEqual(detail.json['batches'][0]['prompt'],'會員測試紀錄')
        self.assertNotIn('member-secret',detail.get_data(as_text=True))
        self.assertEqual(self.b.post(f'/api/admin/members/{bid}/keys').status_code,403)
        keys=self.a.post(f'/api/admin/members/{bid}/keys')
        self.assertEqual(keys.json['current_key'],'member-secret')
        self.assertEqual(keys.headers['Cache-Control'],'no-store')
        with self.app.app_context():
            self.assertEqual(AdminAudit.query.count(),1)
            self.assertEqual(AdminAudit.query.first().target_id,bid)
        token=self.a.post('/api/device/token',json={}).json['device']['code']
        self.assertEqual(self.app.test_client().get('/api/admin/members',headers={'Authorization':'Bearer '+token}).status_code,401)

    def test_admin_can_view_member_photo_but_normal_user_cannot(self):
        upload=self.b.post('/api/upload',data={'photo':(self.photo(),'member.jpg')})
        self.assertEqual(upload.status_code,200)
        url='/api/uploads/'+upload.json['filename']
        self.assertEqual(self.a.get(url).status_code,404)
        with self.app.app_context():
            user=User.query.filter_by(username='alice').first()
            db.session.add(AdminRole(user_id=user.id));db.session.commit()
        self.assertEqual(self.a.get(url).status_code,200)
