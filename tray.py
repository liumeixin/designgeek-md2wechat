#!/usr/bin/env python3
"""
DesignGeek Editor — Windows 托盘程序
========================================
启动 Flask 后台服务 + 系统托盘图标
"""
import sys
import os
import subprocess
import threading
import webbrowser

# 确保工作目录正确
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

import pystray
from PIL import Image, ImageDraw, ImageFont

# 全局变量
tray_icon = None
TASK_NAME = "DesignGeek Editor"
BAT_PATH = os.path.join(SCRIPT_DIR, 'DesignGeek-Editor.bat')

def create_icon_image():
    """创建托盘图标（简洁的 DesignGeek 字标）"""
    size = 128
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    margin = 8
    draw.ellipse([margin, margin, size-margin, size-margin], fill='#4A90D9')
    
    try:
        font = ImageFont.truetype("msyh.ttc", 72)
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), "文", font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - 5
    draw.text((x, y), "文", fill='white', font=font)
    
    return img

def check_autostart():
    """检测开机自启是否已设置"""
    try:
        result = subprocess.run(
            ['schtasks', '/query', '/tn', TASK_NAME],
            capture_output=True, text=True, encoding='gbk', errors='ignore'
        )
        return result.returncode == 0
    except:
        return False

def set_autostart(enable=True):
    """设置或取消开机自启（使用 PowerShell 提升权限）"""
    if enable:
        # 创建计划任务
        ps_cmd = f'''
        $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c ""{BAT_PATH}""'
        $trigger = New-ScheduledTaskTrigger -AtLogon
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName "{TASK_NAME}" -Action $action -Trigger $trigger -Settings $settings -Force
        '''
    else:
        # 删除计划任务
        ps_cmd = f'Unregister-ScheduledTask -TaskName "{TASK_NAME}" -Confirm:$false -ErrorAction SilentlyContinue'
    
    try:
        result = subprocess.run(
            ['powershell', '-Command', ps_cmd],
            capture_output=True, text=True, encoding='utf-8', errors='ignore'
        )
        return result.returncode == 0
    except:
        return False

def on_open_browser(icon, item):
    """打开浏览器"""
    webbrowser.open('http://localhost:18888')

def on_toggle_autostart(icon, item):
    """切换开机自启"""
    current = check_autostart()
    success = set_autostart(not current)
    if success:
        update_menu(icon)

def update_menu(icon):
    """更新菜单（开机自启状态）"""
    autostart_enabled = check_autostart()
    autostart_text = "✓ 已设置开机自启" if autostart_enabled else "设置开机自启"
    
    menu = pystray.Menu(
        pystray.MenuItem('打开 DesignGeek Editor', on_open_browser, default=True),
        pystray.MenuItem(autostart_text, on_toggle_autostart),
        pystray.MenuItem('退出', on_exit)
    )
    icon.menu = menu

def on_exit(icon, item):
    """退出程序"""
    icon.stop()
    os._exit(0)

def start_flask_server():
    """在后台线程启动 Flask 服务"""
    from backend.app import app
    app.run(host='127.0.0.1', port=18888, debug=False, use_reloader=False)

def main():
    global tray_icon
    
    # 检查端口是否已被占用
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 18888))
    sock.close()
    
    if result == 0:
        print("服务已在运行")
    else:
        print("启动 Flask 服务...")
        server_thread = threading.Thread(target=start_flask_server, daemon=True)
        server_thread.start()
        
        import time
        for i in range(10):
            time.sleep(0.5)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 18888))
            sock.close()
            if result == 0:
                print("服务启动成功")
                break
    
    # 创建托盘图标
    icon_image = create_icon_image()
    
    # 创建菜单
    autostart_enabled = check_autostart()
    autostart_text = "✓ 已设置开机自启" if autostart_enabled else "设置开机自启"
    
    menu = pystray.Menu(
        pystray.MenuItem('打开 DesignGeek Editor', on_open_browser, default=True),
        pystray.MenuItem(autostart_text, on_toggle_autostart),
        pystray.MenuItem('退出', on_exit)
    )
    
    tray_icon = pystray.Icon(
        "wenyan-editor",
        icon_image,
        "DesignGeek Editor",
        menu
    )
    
    print("托盘图标已启动")
    tray_icon.run()

if __name__ == '__main__':
    main()
