"""Python API entry point when PHP is hosted separately (e.g. Apache)."""
import os
from app import create_app
application = create_app()
if __name__ == '__main__':
    application.run(host='127.0.0.1', port=int(os.environ.get('API_PORT', '5001')), debug=False)
