#!/bin/bash
# Clasp 전체 빌드 스크립트
# 1. Python 백엔드 PyInstaller 번들
# 2. React 프론트엔드 Vite 빌드와 electron-builder 패키징

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "=== [1/2] Backend PyInstaller 번들 ==="
cd "$BACKEND_DIR"
source venv/bin/activate
pip install pyinstaller --quiet
pyinstaller clasp_backend.spec --distpath dist --workpath build --noconfirm
echo "Backend bundle: $BACKEND_DIR/dist/clasp-backend"

echo "=== [2/2] Frontend 빌드와 Electron 앱 패키징 ==="
# 백엔드 번들을 Electron resources에 복사
rm -rf "$FRONTEND_DIR/resources/backend"
mkdir -p "$FRONTEND_DIR/resources"
cp -R "$BACKEND_DIR/dist/clasp-backend" "$FRONTEND_DIR/resources/backend"

cd "$FRONTEND_DIR"
npm run build:electron

echo "=== 빌드 완료 ==="
echo "결과물: $FRONTEND_DIR/release/"
