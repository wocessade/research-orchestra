@echo off
rem 控制台 glue serve 自启（放入用户启动文件夹，下次登录自动生效；无凭据内容）
rem 用 pythonw：无控制台窗口，不闪黑框（cmd_serve 已做 stdout 空保护）
start "" "C:\Users\19041\AppData\Local\Programs\Python\Python311\pythonw.exe" "D:\pythonProject\orchestra\console\console_feed.py" serve
