import os
import uvicorn
from asgi import app

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('API_PORT', '5001')))
