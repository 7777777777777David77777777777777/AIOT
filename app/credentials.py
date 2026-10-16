"""Server-side credential encryption; keep .credential-key with database backups."""
import os
from pathlib import Path
from cryptography.fernet import Fernet
from app.config import DATA_DIR
from flask import current_app

def cipher():
    key = os.environ.get('CREDENTIAL_ENCRYPTION_KEY')
    if not key:
        path = Path(DATA_DIR) / '.credential-key'
        try:
            with path.open('xb') as f:
                f.write(Fernet.generate_key())
        except FileExistsError:
            pass
        key = path.read_bytes()
    return Fernet(key)

def encrypt(value):
    if not value:
        return None
    if not current_app.config.get('ENCRYPT_STORED_KEYS', False):
        return value
    return 'enc:' + cipher().encrypt(value.encode()).decode()

def decrypt(value):
    if not value:
        return ''
    return cipher().decrypt(value[4:].encode()).decode() if value.startswith('enc:') else value
