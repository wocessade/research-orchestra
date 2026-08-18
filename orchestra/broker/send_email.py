#!/usr/bin/env python3
"""Pi 侧邮件投递（stdlib only）。SMTP 凭据从环境变量读取（systemd drop-in 注入）。
用法: python3 send_email.py "<主题>" <正文文件路径>
"""
import os
import smtplib
import sys
from email.header import Header
from email.mime.text import MIMEText

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: send_email.py <subject> <body-file>", file=sys.stderr)
        return 2
    subject, body_path = sys.argv[1], sys.argv[2]
    user = os.environ.get("SMTP_USER", "")
    pw = os.environ.get("SMTP_PASS", "")
    host = os.environ.get("SMTP_HOST", "smtp.qq.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    to = os.environ.get("SMTP_TO", user or "1904134720@qq.com")
    if not user or not pw:
        print("SMTP_USER/SMTP_PASS 环境变量缺失", file=sys.stderr)
        return 1
    with open(body_path, encoding="utf-8") as f:
        body = f.read()
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = to
    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, pw)
            s.sendmail(user, [to], msg.as_string())
    except Exception as e:
        print(f"send failed: {e}", file=sys.stderr)
        return 1
    print("email sent")
    return 0

if __name__ == "__main__":
    sys.exit(main())
