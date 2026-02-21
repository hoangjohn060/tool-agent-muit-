@echo off
echo Building OpenClaw with Nuitka...

REM Check if Nuitka is installed
python -m nuitka --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Nuitka not found. Installing...
    python -m pip install nuitka zstandard
)

echo.
echo =========================================
echo Building Bridge Server...
echo =========================================
REM Khong an console cua Server (vi can xem log)
python -m nuitka --standalone --output-dir=dist --enable-plugin=tk-inter --include-package=google --include-package=grpc --include-package=telegram --include-package=httpx --include-package=httpcore --assume-yes-for-downloads bridge_server.py

echo.
echo =========================================
echo Building Agent GUI...
echo =========================================
REM An console cua GUI
python -m nuitka --standalone --output-dir=dist --enable-plugin=tk-inter --include-package=google --include-package=grpc --include-package=urllib3 --windows-console-mode=disable --assume-yes-for-downloads agent_gui.py

echo.
echo =========================================
echo Build Complete!
echo Hay vao thu muc 'dist/agent_gui.dist' de mo tool 'agent_gui.exe'
echo Neu ban muon doi ten, ban co the doi 'agent_gui.exe' thanh 'OpenClawManager.exe'
pause
