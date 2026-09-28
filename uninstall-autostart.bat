@echo off
chcp 65001 >nul
title 取消文颜排版器开机自启

echo ========================================
echo   取消文颜排版器开机自启
echo ========================================
echo.

schtasks /delete /tn "文颜排版器" /f

if %errorlevel%==0 (
    echo ✅ 开机自启已取消
) else (
    echo ❌ 取消失败，可能未设置过开机自启
)

echo.
pause
