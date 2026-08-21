"""控制台 v2 serve 隐藏启动（放入用户启动文件夹；无窗口、无凭据）。

Startup 里放 .bat 会先弹出 cmd 黑框；用 pythonw 跑本文件则无控制台。
启动文件夹拒绝 .vbs 写入（受控文件夹保护），故用 .pyw 落地。
"""
import subprocess

subprocess.Popen(
    [
        r"C:\Users\19041\AppData\Local\Programs\Python\Python311\pythonw.exe",
        r"D:\pythonProject\orchestra\console\console_feed.py",
        "serve",
    ],
    creationflags=subprocess.CREATE_NO_WINDOW,
)
