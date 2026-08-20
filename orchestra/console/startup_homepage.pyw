"""控制台 Homepage 隐藏启动（放入用户启动文件夹；无窗口、无凭据）。

用 pythonw 跑本文件：本身无控制台，CREATE_NO_WINDOW 使 start_homepage.bat
（robocopy 同步 + pnpm start）的窗口也不可见。启动文件夹拒绝 .vbs 写入
（受控文件夹保护），故用 .pyw 落地。
"""
import subprocess

subprocess.run(
    [r"D:\pythonProject\orchestra\console\start_homepage.bat"],
    creationflags=subprocess.CREATE_NO_WINDOW,
)
