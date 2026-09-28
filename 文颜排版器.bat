@echo off
chcp 65001 >nul

:: 检查端口是否已被占用
netstat -an | findstr ":18888" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    start http://localhost:18888
    echo 文颜排版器已在运行，已打开浏览器。
    exit /b
)

:: 使用完整路径运行 Python
cd /d "%~dp0"
"C:\Users\liume\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" tray.py

:: 打开浏览器
timeout /t 3 /nobreak >nul
start http://localhost:18888
