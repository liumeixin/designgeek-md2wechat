@echo off
chcp 65001 >nul

:: 检查端口是否已被占用
netstat -an | findstr ":18888" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    start http://localhost:18888
    echo DesignGeek Editor 已在运行，已打开浏览器。
    exit /b
)

cd /d "%~dp0"

:: 优先用仓库自带的 .venv，没有则回落到系统 python
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

:: 托盘方式静默启动
"%PY%" tray.py

:: 打开浏览器
timeout /t 3 /nobreak >nul
start http://localhost:18888
