import os
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from app.config import database_url
from app import create_app
from app.database import db


class PostgresConfigTests(unittest.TestCase):
    def test_render_urls_and_local_fallback(self):
        for prefix in ('postgres://', 'postgresql://'):
            self.assertEqual(database_url(prefix + 'user:pass@host/db?sslmode=require'),
                             'postgresql+psycopg://user:pass@host/db?sslmode=require')
        self.assertEqual(database_url('sqlite://'), 'sqlite://')
        with patch.dict(os.environ, {'RENDER': 'true'}):
            with self.assertRaises(RuntimeError):
                database_url('')
        with patch.dict(os.environ, {'RENDER': 'false'}):
            self.assertTrue(database_url('').startswith('sqlite:///'))

    def test_all_models_compile_for_postgres(self):
        from app import models
        for table in db.metadata.sorted_tables:
            sql = str(CreateTable(table).compile(dialect=postgresql.dialect()))
            self.assertIn('CREATE TABLE', sql)

    @unittest.skipUnless(os.environ.get('TEST_POSTGRES_URL'), 'No isolated PostgreSQL test URL configured')
    def test_live_postgres_isolated_schema(self):
        # An isolated schema keeps real account tables untouched.
        import uuid
        engine = create_engine(database_url(os.environ['TEST_POSTGRES_URL']))
        schema = 'test_' + uuid.uuid4().hex
        from app import models
        try:
            with engine.begin() as conn:
                conn.execute(text('CREATE SCHEMA ' + schema))
                conn.execute(text('SET LOCAL search_path TO ' + schema))
                db.metadata.create_all(conn)
                conn.execute(text("INSERT INTO users (uid, username, password_hash) VALUES ('TEST01', 'postgres-check', 'test-only')"))
                self.assertEqual(conn.execute(text('SELECT uid FROM users')).scalar(), 'TEST01')
        finally:
            with engine.begin() as conn:
                conn.execute(text('DROP SCHEMA IF EXISTS ' + schema + ' CASCADE'))
            engine.dispose()
