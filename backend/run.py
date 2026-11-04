"""
PyInstaller 번들 진입점
uvicorn으로 FastAPI 앱 실행
"""
import os

import uvicorn

from main import app

if __name__ == '__main__':
    uvicorn.run(
        app,
        host='127.0.0.1',
        port=int(os.environ.get('CLASP_PORT', '8000')),
        log_level='warning',
    )
