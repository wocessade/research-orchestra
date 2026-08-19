#!/usr/bin/env python3
"""Pi 侧邮件投递（stdlib only）。SMTP 凭据从环境变量读取（systemd drop-in 注入）。
用法: python3 send_email.py "<主题>" <正文文件路径>
"""
import os
import smtplib
import sys
from email.header import Header
from email.mime.text import MIMEText

NOT_SENT_EXIT_CODE = 10

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: send_email.py <subject> <body-file>", file=sys.stderr)
        return 2
    subject, body_path = sys.argv[1], sys.argv[2]
    user = os.environ.get("SMTP_USER", "")
    pw = os.environ.get("SMTP_PASS", "")
    host = os.environ.get("SMTP_HOST", "smtp.qq.com")
    try:
        port = int(os.environ.get("SMTP_PORT", "465"))
    except ValueError:
        print("SMTP_PORT 非法", file=sys.stderr)
        return NOT_SENT_EXIT_CODE
    to = os.environ.get("SMTP_TO", user or "1904134720@qq.com")
    if not user or not pw:
        print("SMTP_USER/SMTP_PASS 环境变量缺失", file=sys.stderr)
        return NOT_SENT_EXIT_CODE
    try:
        with open(body_path, encoding="utf-8") as f:
            body = f.read()
    except OSError as e:
        print(f"body read failed before send: {e}", file=sys.stderr)
        return NOT_SENT_EXIT_CODE
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = to
    try:
        s = smtplib.SMTP_SSL(host, port, timeout=30)
        s.login(user, pw)
    except Exception as e:
        print(f"SMTP setup failed before send: {e}", file=sys.stderr)
        return NOT_SENT_EXIT_CODE
    try:
        with s:
            s.sendmail(user, [to], msg.as_string())
    except Exception as e:
        print(f"send failed: {e}", file=sys.stderr)
        return 1
    print("email sent")
    return 0

if __name__ == "__main__":
    sys.exit(main())
