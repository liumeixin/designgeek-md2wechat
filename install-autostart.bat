@echo off
chcp 65001 >nul
title 安装文颜排版器开机自启

echo ========================================
echo   安装文颜排版器开机自启
echo ========================================
echo.

:: 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
set "BAT_PATH=%SCRIPT_DIR%文颜排版器.bat"

:: 创建计划任务（用户登录时自动启动）
echo 正在创建计划任务...
schtasks /create /tn "文颜排版器" /tr "\"%BAT_PATH%\"" /sc ONLOGON /rl HIGHEST /f

if %errorlevel%==0 (
    echo.
    echo ✅ 开机自启已设置！
    echo    任务名称：文颜排版器
    echo    触发器：用户登录时
) else (
    echo.
    echo ❌ 设置失败，请以管理员身份运行此脚本
)

echo.
echo 如需取消开机自启，运行 uninstall-autostart.bat
echo.
pause
