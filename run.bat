@echo off
chcp 65001
title DesignGeek Editor

echo ========================================
echo   DesignGeek Editor
echo ========================================
echo.

cd /d "%~dp0"

.venv\Scripts\python.exe backend/app.py
