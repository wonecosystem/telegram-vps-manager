#!/usr/bin/env python3
"""Relatório diário enviado pelo cron às 08h."""
import subprocess
import requests
import json
import re
import os
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
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15).stdout
    except:
        return "erro"

def send(text):
    requests.post(f"{API}/sendMessage", data={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }, timeout=10)

def get_active_jails():
    out   = run("fail2ban-client status")
    match = re.search(r"Jail list:\s+(.+)", out)
    if not match:
        return []
    return [j.strip() for j in match.group(1).split(",") if j.strip()]

def main():
    if not TOKEN or not CHAT_ID:
        print("TOKEN ou chat_id não configurado.")
        return

    now   = datetime.now().strftime("%d/%m/%Y %H:%M")
    jails = get_active_jails()

    jail_lines   = []
    total_banned = 0
    if jails:
        for jail in jails:
            out    = run(f"fail2ban-client status {jail}")
            banned = re.search(r"Currently banned:\s+(\d+)", out)
            failed = re.search(r"Currently failed:\s+(\d+)", out)
            b = banned.group(1) if banned else "?"
            f = failed.group(1) if failed else "?"
            total_banned += int(b) if b.isdigit() else 0
            icon = "🔴" if b.isdigit() and int(b) > 0 else "🟢"
            jail_lines.append(f"{icon} `{jail}`: banidos `{b}` | falhas `{f}`")
    else:
        jail_lines.append("_Fail2Ban não instalado ou sem jails ativos._")

    mem      = run("free -h").split("\n")
    mem_line = mem[1].split() if len(mem) > 1 else []
    mem_used  = mem_line[2] if len(mem_line) > 2 else "?"
    mem_total = mem_line[1] if len(mem_line) > 1 else "?"

    disk      = run("df -h /").split("\n")
    disk_line = disk[1].split() if len(disk) > 1 else []
    disk_used = disk_line[2] if len(disk_line) > 2 else "?"
    disk_pct  = disk_line[4] if len(disk_line) > 4 else "?"

    uptime = run("uptime -p").strip()
    load   = run("cat /proc/loadavg").strip().split()[:3]

    candidates = [
        ("ssh","🔐 SSH"), ("nginx","🌍 Nginx"), ("apache2","🌍 Apache2"),
        ("mysql","🗄️ MySQL"), ("mariadb","🗄️ MariaDB"), ("postgresql","🗄️ PostgreSQL"),
        ("docker","🐳 Docker"), ("fail2ban","🔒 Fail2Ban"), ("cron","⏱️ Cron"),
    ]
    svc_lines = []
    seen = set()
    for svc, label in candidates:
        if svc in seen:
            continue
        out = run(f"systemctl list-units --full --all --no-pager {svc}.service 2>/dev/null | grep -c '{svc}.service'").strip()
        if out == "0" or not out:
            continue
        base = label.split()[1]
        if base in seen:
            continue
        seen.add(base)
        seen.add(svc)
        status = run(f"systemctl is-active {svc}").strip()
        icon = "✅" if status == "active" else "❌"
        svc_lines.append(f"{icon} {label}")

    f2b_section = f"🔒 *Fail2Ban — {total_banned} IPs banidos:*\n" + "\n".join(jail_lines) if jails else "🔒 *Fail2Ban:* _não instalado ou sem jails ativos_"

    msg = (
        f"📊 *Relatório Diário*\n"
        f"📅 {now}\n\n"
        f"⏱️ *Uptime:* {uptime}\n"
        f"⚡ *Load:* `{' | '.join(load)}`\n"
        f"💾 *RAM:* `{mem_used}/{mem_total}`\n"
        f"💿 *Disco:* `{disk_used} ({disk_pct})`\n\n"
        f"⚙️ *Serviços:*\n" + "\n".join(svc_lines) + "\n\n"
        f"{f2b_section}"
    )
    send(msg)
    print(f"Relatório enviado para {CHAT_ID}")

if __name__ == "__main__":
    main()
