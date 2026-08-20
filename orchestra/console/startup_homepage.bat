@echo off
rem 控制台 Homepage 自启（放入用户启动文件夹，下次登录自动生效；无凭据内容）
rem start_homepage.bat 内含 robocopy 配置同步（/MIR 会清除目标目录多余文件）
start /min "orchestra-console-homepage" cmd /c "D:\pythonProject\orchestra\console\start_homepage.bat"
