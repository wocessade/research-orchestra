@echo off
rem 控制台启动脚本：同步配置到 Homepage app 并启动（无凭据内容）
robocopy "D:\pythonProject\orchestra\console\homepage" "D:\Apps\homepage\config" /MIR /NFL /NDL /NJH /NJS >nul
cd /d D:\Apps\homepage
set HOMEPAGE_ALLOWED_HOSTS=localhost:3000
pnpm start
