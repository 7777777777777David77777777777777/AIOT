from unittest.mock import patch, Mock
from test_system import SystemTests
from app.models.connection import ModelConnection
from app.credentials import decrypt


class ConnectionTests(SystemTests):
    def test_named_history_and_isolation(self):
        models = [{"id": "gemini-2.5-flash", "name": "Flash"}, {"id": "gemini-2.5-pro", "name": "Pro"}]
        with patch('app.views.connection_view.list_models', return_value=models):
            first = self.a.post('/api/connections', json={'name': '課堂', 'api_key': 'secret-one', 'model': models[0]['id']})
            self.assertEqual(first.status_code, 200)
            second = self.a.post('/api/connections', json={'name': '詳細解題', 'api_key': 'secret-two', 'model': models[1]['id']})
            self.assertEqual(second.status_code, 200)
            cid = first.json['connection']['id']
            self.assertEqual(self.b.post(f'/api/connections/{cid}/activate', json={}).status_code, 404)
            self.assertEqual(self.b.get('/api/connections').json['connections'], [])
            self.assertEqual(self.a.post(f'/api/connections/{cid}/activate', json={}).status_code, 200)
            history = self.a.get('/api/connections').json['connections']
            self.assertEqual(len(history), 2)
            self.assertEqual(sum(c['active'] for c in history), 1)
            self.assertNotIn('secret', str(history))
            bad = self.a.post('/api/connections', json={'name': '錯誤版本', 'model': 'invalid'})
            self.assertEqual(bad.status_code, 400)
        with self.app.app_context():
            active = ModelConnection.query.filter_by(active=True).first()
            self.assertNotEqual(active.api_key, 'secret-one')
            self.assertEqual(decrypt(active.api_key), 'secret-one')
        # Assert the selected model and key reach the solver without a real model call.
        with patch('app.controllers.solver_controller.SolverController.process_solution', return_value={'questions': [{'number': '1', 'question': '求值'}]}) as solver:
            result = self.a.post('/api/solve', data={'images[]': (self.photo(), 'q.jpg')})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(solver.call_args.kwargs['model_name'], models[0]['id'])
            self.assertEqual(solver.call_args.kwargs['api_key'], 'secret-one')

    def test_model_catalog_pagination_and_filter(self):
        first = Mock(status_code=200)
        first.json.return_value = {'models': [{'name': 'models/gemini-2.5-flash', 'supportedGenerationMethods': ['generateContent']}, {'name': 'models/gemini-2.5-flash-tts', 'supportedGenerationMethods': ['generateContent']}], 'nextPageToken': 'next'}
        second = Mock(status_code=200)
        second.json.return_value = {'models': [{'name': 'models/text-embedding', 'supportedGenerationMethods': ['embedContent']}]}
        with patch('app.views.connection_view.requests.get', side_effect=[first, second]) as get:
            result = self.a.post('/api/connections/models', json={'api_key': 'catalog-secret'})
            self.assertEqual([m['id'] for m in result.json['models']], ['gemini-2.5-flash'])
            self.assertEqual(get.call_args.kwargs['params']['pageToken'], 'next')
            self.assertNotIn('catalog-secret', result.get_data(as_text=True))
        self.assertEqual(self.app.test_client().get('/api/connections').status_code, 401)
