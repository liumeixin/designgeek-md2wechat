@echo off
chcp 65001
title 文颜 Markdown 排版器

echo ========================================
echo   文颜 Markdown 排版器
echo ========================================
echo.

cd /d "%~dp0"

.venv\Scripts\python.exe backend/app.py
