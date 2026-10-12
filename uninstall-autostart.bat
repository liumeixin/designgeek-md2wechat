@echo off
chcp 65001 >nul
title 取消 DesignGeek Editor 开机自启

echo ========================================
echo   取消 DesignGeek Editor 开机自启
echo ========================================
echo.

schtasks /delete /tn "DesignGeek Editor" /f
:: 顺带清掉改名前的旧任务
schtasks /delete /tn "文颜排版器" /f >nul 2>&1

if %errorlevel%==0 (
    echo ✅ 开机自启已取消
) else (
    echo ❌ 取消失败，可能未设置过开机自启
)

echo.
pause
