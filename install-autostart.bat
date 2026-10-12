@echo off
chcp 65001 >nul
title 安装 DesignGeek Editor 开机自启

echo ========================================
echo   安装 DesignGeek Editor 开机自启
echo ========================================
echo.

:: 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
set "BAT_PATH=%SCRIPT_DIR%DesignGeek-Editor.bat"

:: 2026-10-12 改名：先清掉旧任务「文颜排版器」，否则会留下指向已不存在文件的僵尸任务
schtasks /delete /tn "文颜排版器" /f >nul 2>&1

:: 创建计划任务（用户登录时自动启动）
echo 正在创建计划任务...
schtasks /create /tn "DesignGeek Editor" /tr "\"%BAT_PATH%\"" /sc ONLOGON /rl HIGHEST /f

if %errorlevel%==0 (
    echo.
    echo ✅ 开机自启已设置！
    echo    任务名称：DesignGeek Editor
    echo    触发器：用户登录时
) else (
    echo.
    echo ❌ 设置失败，请以管理员身份运行此脚本
)

echo.
echo 如需取消开机自启，运行 uninstall-autostart.bat
echo.
pause
