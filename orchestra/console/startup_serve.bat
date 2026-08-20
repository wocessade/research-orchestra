@echo off
rem 控制台 glue serve 自启（放入用户启动文件夹，下次登录自动生效；无凭据内容）
start /min "orchestra-console-serve" "C:\Users\19041\AppData\Local\Programs\Python\Python311\python.exe" "D:\pythonProject\orchestra\console\console_feed.py" serve
