#!/usr/bin/env python3
"""Enviado automaticamente após reboot do servidor."""
import subprocess
import requests
import json
import os
import time
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

cfg     = load_config()
TOKEN   = cfg.get("token", "")
CHAT_ID = cfg.get("chat_id")
API     = f"https://api.telegram.org/bot{TOKEN}"

def run(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15).stdout.strip()
    except:
        return "erro"

def send(text):
    for attempt in range(5):
        try:
            r = requests.post(f"{API}/sendMessage", data={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            }, timeout=10)
            if r.status_code == 200:
                return
        except:
            pass
        time.sleep(5)

def main():
    if not TOKEN or not CHAT_ID:
        return

    time.sleep(15)

    now    = datetime.now().strftime("%d/%m/%Y %H:%M")
    uptime = run("uptime -p")

    services = [
        ("exim4",            "📧 Exim4"),
        ("spamd",            "🛡️ SpamAssassin"),
        ("clamav-daemon",    "🦠 ClamAV"),
        ("clamav-freshclam", "🔄 Freshclam"),
        ("dovecot",          "📬 Dovecot"),
        ("bind9",            "🌐 BIND9"),
        ("fail2ban",         "🔒 Fail2Ban"),
        ("nginx",            "🌍 Nginx"),
        ("hestia",           "⚙️ HestiaCP"),
        ("mariadb",          "🗄️ MariaDB"),
    ]

    lines  = [f"✅ *Servidor reiniciado com sucesso!*\n📅 {now}\n⏱️ {uptime}\n"]
    all_ok = True
    for svc, label in services:
        status = run(f"systemctl is-active {svc}")
        icon   = "✅" if status == "active" else "❌"
        if status != "active":
            all_ok = False
        lines.append(f"{icon} {label}: `{status}`")

    lines.append("\n🟢 *Todos os serviços estão operacionais.*" if all_ok
                 else "\n🔴 *Atenção: um ou mais serviços não iniciaram corretamente!*")

    send("\n".join(lines))

if __name__ == "__main__":
    main()
