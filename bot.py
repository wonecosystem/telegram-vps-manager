#!/usr/bin/env python3
import subprocess
import requests
import time
import json
import os
import re
import logging
import threading
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# ─── Config ────────────────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

cfg = load_config()
TOKEN = cfg.get("token", "")
if not TOKEN:
    raise SystemExit("❌ TOKEN não configurado em config.json")

API = f"https://api.telegram.org/bot{TOKEN}"

AUTHORIZED_CHAT_ID   = cfg.get("chat_id")
CPU_ALERT_THRESHOLD  = cfg.get("cpu_alert_threshold", 80)
DISK_ALERT_THRESHOLD = cfg.get("disk_alert_threshold", 80)
MONITOR_INTERVAL     = cfg.get("monitor_interval", 300)

logging.basicConfig(
    filename=os.path.join(BASE_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# ─── Telegram helpers ──────────────────────────────────────────────────────────

def send(chat_id, text, parse_mode="Markdown"):
    try:
        r = requests.post(f"{API}/sendMessage", data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }, timeout=10)
        return r.json()
    except Exception as e:
        logging.error(f"send error: {e}")

def send_buttons(chat_id, text, buttons, parse_mode="Markdown"):
    try:
        r = requests.post(f"{API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": {"inline_keyboard": buttons}
        }, timeout=10)
        return r.json()
    except Exception as e:
        logging.error(f"send_buttons error: {e}")

def answer_callback(callback_id, text=""):
    try:
        requests.post(f"{API}/answerCallbackQuery", json={
            "callback_query_id": callback_id,
            "text": text
        }, timeout=10)
    except Exception as e:
        logging.error(f"answer_callback error: {e}")

def get_updates(offset=None):
    try:
        r = requests.get(f"{API}/getUpdates", params={
            "timeout": 30,
            "offset": offset
        }, timeout=35)
        return r.json()
    except Exception as e:
        logging.error(f"get_updates error: {e}")
        return {"ok": False, "result": []}

def set_commands():
    commands = [
        {"command": "start",      "description": "Menu principal"},
        {"command": "menu",       "description": "Menu principal"},
        {"command": "monitoramento","description": "Menu de monitoramento"},
        {"command": "manutencao",  "description": "Menu de manutenção"},
        {"command": "status",     "description": "CPU, RAM, disco e uptime"},
        {"command": "servicos",   "description": "Status dos serviços"},
        {"command": "processos",  "description": "Top processos por CPU e RAM"},
        {"command": "rede",       "description": "IP público, interfaces e portas"},
        {"command": "ping",       "description": "Ping e rota com 5 saltos: /ping host"},
        {"command": "dns",        "description": "Consulta DNS do domínio: /dns dominio.com"},
        {"command": "disco",      "description": "Uso detalhado de disco"},
        {"command": "logs",       "description": "Logs do sistema"},
        {"command": "erros",      "description": "Últimos erros do sistema (journalctl)"},
        {"command": "docker",     "description": "Status dos containers Docker"},
        {"command": "seguranca",  "description": "Menu de segurança (Fail2Ban, Firewall, etc)"},
        {"command": "banned",     "description": "IPs banidos agora"},
        {"command": "unban",      "description": "Desbanir IP: /unban 1.2.3.4"},
        {"command": "firewall",   "description": "Gerenciar firewall (UFW)"},
        {"command": "controle",   "description": "Controlar serviços (iniciar/parar/reiniciar)"},
        {"command": "instalar",   "description": "Instalar aplicações no servidor"},
        {"command": "atualizacoes","description": "Listar pacotes pendentes de atualização"},
        {"command": "atualizar",  "description": "Atualizar pacotes do servidor"},
        {"command": "reboot",     "description": "Reiniciar o servidor (pede confirmação)"},
    ]
    requests.post(f"{API}/setMyCommands", json={"commands": commands}, timeout=10)

# ─── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15).stdout
    except Exception as e:
        return str(e)

def now():
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def is_installed(pkg):
    variants = [pkg, f"{pkg}-client", f"{pkg}-server"]
    for v in variants:
        r = subprocess.run(f"command -v {v}", shell=True, capture_output=True)
        if r.returncode == 0:
            return True
    return False

# ─── Monitoramento — Menu ──────────────────────────────────────────────────────

def cmd_monitoramento(chat_id):
    buttons = [
        [
            {"text": "🖥️ Status",     "callback_data": "mon_status"},
            {"text": "⚙️ Serviços",   "callback_data": "mon_servicos"},
        ],
        [
            {"text": "🔝 Processos",  "callback_data": "mon_processos"},
            {"text": "🌐 Rede",       "callback_data": "mon_rede"},
        ],
        [
            {"text": "📡 Ping",       "callback_data": "mon_ping"},
            {"text": "🔍 DNS",        "callback_data": "mon_dns"},
        ],
        [
            {"text": "💿 Disco",      "callback_data": "mon_disco"},
            {"text": "📜 Logs",       "callback_data": "mon_logs"},
        ],
        [
            {"text": "🚨 Erros",      "callback_data": "mon_erros"},
            {"text": "🐳 Docker",     "callback_data": "mon_docker"},
        ],
        [
            {"text": "🏠 Menu Principal", "callback_data": "cmd_start"},
        ],
    ]
    send_buttons(chat_id,
        "🖥️ *Menu de Monitoramento*\n\n"
        "Escolha uma opção:",
        buttons
    )


# ─── Monitoramento ─────────────────────────────────────────────────────────────

def cmd_start(chat_id, user):
    global AUTHORIZED_CHAT_ID
    config = load_config()
    if "chat_id" not in config:
        config["chat_id"] = chat_id
        save_config(config)
        AUTHORIZED_CHAT_ID = chat_id
        logging.info(f"Chat ID registrado: {chat_id}")

    name = user.get("first_name", "Admin")
    buttons = [
        [
            {"text": "🖥️ Monitoramento", "callback_data": "menu_monitoramento"},
            {"text": "🔒 Segurança",     "callback_data": "menu_seguranca"},
        ],
        [
            {"text": "📦 Instalações",   "callback_data": "menu_instalar"},
            {"text": "⚙️ Manutenção",   "callback_data": "menu_manutencao"},
        ],
    ]
    send_buttons(chat_id,
        f"👋 Olá, *{name}*! Sou o bot do servidor.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Escolha uma opção:\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 _Relatório diário automático às 08h._\n"
        f"⚠️ _Alertas de CPU e disco acima de {CPU_ALERT_THRESHOLD}%._",
        buttons
    )


def cmd_status(chat_id):
    uptime = run("uptime -p").strip()
    load   = run("cat /proc/loadavg").strip().split()[:3]

    mem      = run("free -h").split("\n")
    mem_line = mem[1].split() if len(mem) > 1 else []
    mem_total = mem_line[1] if len(mem_line) > 1 else "?"
    mem_used  = mem_line[2] if len(mem_line) > 2 else "?"
    mem_free  = mem_line[3] if len(mem_line) > 3 else "?"

    disk      = run("df -h /").split("\n")
    disk_line = disk[1].split() if len(disk) > 1 else []
    disk_total = disk_line[1] if len(disk_line) > 1 else "?"
    disk_used  = disk_line[2] if len(disk_line) > 2 else "?"
    disk_free  = disk_line[3] if len(disk_line) > 3 else "?"
    disk_pct   = disk_line[4] if len(disk_line) > 4 else "?"

    cpu     = get_cpu_usage()
    cpu_str = f"{cpu:.1f}%" if cpu is not None else "?"

    msg = (
        f"🖥️ *Status do Servidor*\n"
        f"📅 {now()}\n\n"
        f"⏱️ *Uptime:* {uptime}\n"
        f"⚡ *Load avg:* `{' | '.join(load)}`\n"
        f"🔥 *CPU uso:* `{cpu_str}`\n\n"
        f"💾 *RAM:*\n"
        f"  Total: `{mem_total}` | Usado: `{mem_used}` | Livre: `{mem_free}`\n\n"
        f"💿 *Disco (/):*\n"
        f"  Total: `{disk_total}` | Usado: `{disk_used}` | Livre: `{disk_free}` ({disk_pct})"
    )
    send(chat_id, msg)


def cmd_servicos(chat_id):
    candidates = [
        ("ssh",        "🔐 SSH"),
        ("nginx",      "🌍 Nginx"),
        ("apache2",    "🌍 Apache2"),
        ("mysql",      "🗄️ MySQL"),
        ("mariadb",    "🗄️ MariaDB"),
        ("postgresql", "🗄️ PostgreSQL"),
        ("docker",     "🐳 Docker"),
        ("fail2ban",   "🔒 Fail2Ban"),
        ("cron",       "⏱️ Cron"),
    ]
    lines = [f"⚙️ *Status dos Serviços*\n📅 {now()}\n"]
    found = False
    seen  = set()
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
        lines.append(f"{icon} {label}: `{status}`")
        found = True
    if not found:
        lines.append("_Nenhum serviço conhecido encontrado._")
    send(chat_id, "\n".join(lines))


def cmd_controle_servicos(chat_id):
    candidates = [
        ("ssh",        "🔐 SSH"),
        ("nginx",      "🌍 Nginx"),
        ("apache2",    "🌍 Apache2"),
        ("mysql",      "🗄️ MySQL"),
        ("mariadb",    "🗄️ MariaDB"),
        ("postgresql", "🗄️ PostgreSQL"),
        ("docker",     "🐳 Docker"),
        ("fail2ban",   "🔒 Fail2Ban"),
        ("cron",       "⏱️ Cron"),
    ]

    lines = ["🔧 *Controle de Serviços*\n"]
    buttons = []
    seen = set()

    for svc, emoji in candidates:
        if svc in seen:
            continue
        result = subprocess.run(
            f"systemctl list-units --type=service --all --quiet {svc}.service 2>/dev/null",
            shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            continue

        seen.add(svc)
        status = run(f"systemctl is-active {svc}").strip()
        icon = "🟢" if status == "active" else "🔴"
        lines.append(f"{icon} {emoji} {svc.capitalize()}")
        buttons.append({"text": f"⚙️ {emoji} {svc.capitalize()}", "callback_data": f"svc_menu_{svc}"})

    if len(buttons) == 0:
        send(chat_id, "Nenhum serviço detectado no servidor.")
        return

    buttons_grid = [[buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]] for i in range(0, len(buttons), 2)]
    send_buttons(chat_id, "\n".join(lines), buttons_grid)


def cb_svc_menu(chat_id, svc):
    status = run(f"systemctl is-active {svc}").strip()
    icon = "🟢" if status == "active" else "🔴"

    msg = f"⚙️ *{svc.capitalize()}*\n\nStatus: {icon} {status.upper()}"
    buttons = []

    if status != "active":
        buttons.append({"text": "▶️ Iniciar", "callback_data": f"svc_start_{svc}"})
    if status == "active":
        buttons.append({"text": "⏹ Parar", "callback_data": f"svc_stop_{svc}"})

    buttons.append({"text": "🔄 Reiniciar", "callback_data": f"svc_restart_{svc}"})
    buttons.append({"text": "◀️ Voltar", "callback_data": "cmd_controle"})

    buttons_grid = [[buttons[i], buttons[i+1]] if i+1 < len(buttons) else [buttons[i]] for i in range(0, len(buttons), 2)]
    send_buttons(chat_id, msg, buttons_grid)


def cb_svc_confirmar(chat_id, action, svc):
    msg = f"⚠️ *Confirma {action.upper()} do {svc.capitalize()}?*"
    buttons = [
        [
            {"text": "✅ Sim", "callback_data": f"svc_do_{action}_{svc}"},
            {"text": "❌ Cancelar", "callback_data": "install_cancel"},
        ]
    ]
    send_buttons(chat_id, msg, buttons)


def cb_svc_executar(chat_id, action, svc):
    try:
        result = subprocess.run(
            f"systemctl {action} {svc}",
            shell=True, capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL
        )
        if result.returncode == 0:
            send(chat_id, f"✅ *{svc.capitalize()} {action}* executado com sucesso!")
        else:
            erro = result.stderr or result.stdout or "Sem detalhes"
            if "not found" in erro.lower() or "could not be found" in erro.lower():
                cb_svc_install_options(chat_id, svc)
            else:
                send(chat_id, f"❌ *Erro ao {action} {svc}*\n\n```\n{erro[-500:]}\n```")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — Operação excedeu o tempo limite.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")


SERVICE_PACKAGES = {
    "nginx": "nginx",
    "apache2": "apache2",
    "mysql": "mysql-server",
    "mariadb": "mariadb-server",
    "postgresql": "postgresql",
    "docker": "docker.io",
    "fail2ban": "fail2ban",
}


def cb_svc_install_options(chat_id, svc):
    package = SERVICE_PACKAGES.get(svc, svc)
    msg = (
        f"❌ *{svc.capitalize()} não está instalado*\n\n"
        f"Para instalar, você pode:\n\n"
        f"**Opção 1 — Instalação automática:**\n"
        f"Clique no botão 📥 Instalar\n\n"
        f"**Opção 2 — Instalar manualmente:**\n"
        f"```\n"
        f"sudo apt update\n"
        f"sudo apt install -y {package}\n"
        f"```"
    )
    buttons = [
        [
            {"text": "📥 Instalar Automaticamente", "callback_data": f"svc_install_auto_{svc}"},
            {"text": "◀️ Voltar", "callback_data": f"svc_menu_{svc}"},
        ]
    ]
    send_buttons(chat_id, msg, buttons)


def cb_svc_install_auto(chat_id, svc):
    package = SERVICE_PACKAGES.get(svc, svc)
    send(chat_id, f"⏳ *Instalando {svc.capitalize()}...*\n\nIsso pode levar alguns minutos.")

    try:
        result = subprocess.run(
            f"apt update && apt install -y {package}",
            shell=True, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL
        )
        if result.returncode == 0:
            send(chat_id, f"✅ *{svc.capitalize()} instalado com sucesso!*\n\n🔄 Tentando iniciar o serviço...")
            time.sleep(2)
            result2 = subprocess.run(
                f"systemctl start {svc}",
                shell=True, capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL
            )
            if result2.returncode == 0:
                send(chat_id, f"✅ *{svc.capitalize()} iniciado com sucesso!*")
            else:
                send(chat_id, f"⚠️ *{svc.capitalize()} instalado, mas houve um erro ao iniciar.*\n\nTente: `systemctl start {svc}`")
        else:
            erro = result.stderr or result.stdout or "Erro desconhecido"
            send(chat_id, f"❌ *Erro na instalação*\n\n```\n{erro[-500:]}\n```")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — Instalação excedeu o tempo limite.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")


def cmd_processos(chat_id):
    header = f"{'PROCESSO':<22} {'CPU%':>5} {'MEM%':>5}"
    cpu_out = run(
        "ps aux --sort=-%cpu | awk 'NR>1 {printf \"%-22s %5s %5s\\n\", $11, $3, $4}' | head -6"
    ).strip()
    mem_out = run(
        "ps aux --sort=-%mem | awk 'NR>1 {printf \"%-22s %5s %5s\\n\", $11, $3, $4}' | head -6"
    ).strip()
    msg = (
        f"🔝 *Top Processos*\n📅 {now()}\n\n"
        f"🔥 *Por CPU:*\n```\n{header}\n{cpu_out}\n```\n\n"
        f"💾 *Por RAM:*\n```\n{header}\n{mem_out}\n```"
    )
    send(chat_id, msg)


def cmd_rede(chat_id):
    pub_ip     = run("curl -s --max-time 5 ifconfig.me || curl -s --max-time 5 icanhazip.com").strip()
    interfaces = run("ip -br addr show").strip()
    ports      = run("ss -tlnp | awk 'NR>1 {print $1, $4, $6}' | column -t").strip()
    msg = (
        f"🌐 *Rede*\n📅 {now()}\n\n"
        f"🔌 *IP Público:* `{pub_ip or 'não detectado'}`\n\n"
        f"📡 *Interfaces:*\n```\n{interfaces}\n```\n\n"
        f"🔓 *Portas em escuta:*\n```\n{ports or 'nenhuma detectada'}\n```"
    )
    send(chat_id, msg)


def cmd_ping(chat_id, host):
    if not host:
        send(chat_id, "⚠️ Use: `/ping google.com` ou `/ping 8.8.8.8`")
        return
    # Valida host: domínio ou IP
    if not re.match(r"^[a-zA-Z0-9\.\-]+$", host):
        send(chat_id, "⚠️ Host inválido.")
        return
    send(chat_id, f"📡 *Testando rota para `{host}`...*")
    ping_out = run(f"ping -c 4 -W 2 {host} 2>&1")
    trace_out = run(f"tracepath -m 5 {host} 2>&1")
    if not ping_out and not trace_out:
        send(chat_id, f"❌ Host `{host}` inacessível ou não resolvido.")
        return
    # Extrai resumo do ping
    summary = ""
    for line in ping_out.splitlines():
        if "packets transmitted" in line or "rtt" in line or "round-trip" in line:
            summary += line.strip() + "\n"
    msg = (
        f"📡 *Ping & Rota — `{host}`*\n📅 {now()}\n\n"
        f"🏓 *Ping (4 pacotes):*\n```\n{summary.strip() or ping_out[-800:].strip()}\n```\n\n"
        f"🛤️ *Rota (máx. 5 saltos):*\n```\n{trace_out[-1200:].strip()}\n```"
    )
    send(chat_id, msg)


def cmd_dns(chat_id, domain):
    if not domain:
        send(chat_id, "⚠️ Use: `/dns woncloud.com.br` ou `/dns google.com`")
        return
    if not re.match(r"^[a-zA-Z0-9\.\-]+$", domain):
        send(chat_id, "⚠️ Domínio inválido.")
        return
    send(chat_id, f"🔍 *Consultando DNS para `{domain}`...*")

    def dig(tipo):
        return run(f"dig +noall +answer +ttl {domain} {tipo} 2>/dev/null").strip()

    a     = dig("A")
    aaaa  = dig("AAAA")
    mx    = dig("MX")
    ns    = dig("NS")
    txt   = dig("TXT")
    cname = dig("CNAME")

    def fmt(label, raw):
        if not raw:
            return f"  _nenhum registro_"
        lines = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 5:
                ttl, rtype, value = parts[1], parts[3], " ".join(parts[4:])
                lines.append(f"  `{value}` _(TTL {ttl}s)_")
            else:
                lines.append(f"  `{line}`")
        return "\n".join(lines)

    msg = (
        f"🌐 *DNS — `{domain}`*\n📅 {now()}\n\n"
        f"📌 *A (IPv4):*\n{fmt('A', a)}\n\n"
    )
    if aaaa:
        msg += f"📌 *AAAA (IPv6):*\n{fmt('AAAA', aaaa)}\n\n"
    if cname:
        msg += f"🔀 *CNAME:*\n{fmt('CNAME', cname)}\n\n"
    if mx:
        msg += f"📧 *MX (e-mail):*\n{fmt('MX', mx)}\n\n"
    if ns:
        msg += f"🔧 *NS (nameservers):*\n{fmt('NS', ns)}\n\n"
    if txt:
        txt_short = txt[:800] + "..." if len(txt) > 800 else txt
        msg += f"📝 *TXT (SPF/DKIM etc):*\n```\n{txt_short}\n```"

    send(chat_id, msg)


def cmd_disco(chat_id):
    out = run("df -h")
    send(chat_id, f"💿 *Uso de Disco*\n📅 {now()}\n\n```\n{out}```")


def cmd_logs(chat_id):
    buttons = [
        [{"text": "🔐 Auth — logins SSH",    "callback_data": "logs_auth"}],
        [{"text": "⚙️ Syslog",               "callback_data": "logs_syslog"}],
        [{"text": "💻 Dmesg (hardware)",     "callback_data": "logs_dmesg"}],
    ]
    send_buttons(chat_id, "📜 *Logs do Sistema*\n\nQual log deseja visualizar?", buttons)

def cb_logs(chat_id, tipo):
    opcoes = {
        "auth":   ("/var/log/auth.log", "🔐 Auth Log (SSH/login)"),
        "syslog": ("/var/log/syslog",   "⚙️ Syslog"),
        "dmesg":  (None,                "💻 Dmesg"),
    }
    path, label = opcoes.get(tipo, (None, "Log"))
    out = run("dmesg | tail -30") if tipo == "dmesg" else run(f"tail -30 {path} 2>/dev/null || echo 'Arquivo não encontrado'")
    if len(out) > 3500:
        out = out[-3500:]
    send(chat_id, f"📜 *{label}*\n📅 {now()}\n\n```\n{out or 'Sem dados'}\n```")


# ─── Segurança — Fail2Ban ──────────────────────────────────────────────────────

def _fail2ban_not_installed(chat_id):
    send_buttons(chat_id,
        "⚠️ *Fail2Ban não está instalado*\n\n"
        "Este recurso requer o Fail2Ban para funcionar.\n"
        "Deseja instalar agora?",
        [[{"text": "📦 Instalar Fail2Ban", "callback_data": "install_fail2ban_info"},
          {"text": "❌ Cancelar",          "callback_data": "install_cancel"}]]
    )

def get_active_jails():
    out   = run("fail2ban-client status")
    match = re.search(r"Jail list:\s+(.+)", out)
    if not match:
        return []
    return [j.strip() for j in match.group(1).split(",") if j.strip()]

def cmd_fail2ban(chat_id):
    if not is_installed("fail2ban"):
        _fail2ban_not_installed(chat_id)
        return
    jails = get_active_jails()
    if not jails:
        send(chat_id,
            "⚠️ *Fail2Ban está instalado mas não há jails ativos.*\n\n"
            "Verifique se o serviço está rodando:\n"
            "`systemctl status fail2ban`"
        )
        return
    lines        = [f"🔒 *Relatório Fail2Ban*\n📅 {now()}\n"]
    total_banned = 0
    for jail in jails:
        out    = run(f"fail2ban-client status {jail}")
        failed = re.search(r"Currently failed:\s+(\d+)", out)
        banned = re.search(r"Currently banned:\s+(\d+)", out)
        t_fail = re.search(r"Total failed:\s+(\d+)", out)
        t_ban  = re.search(r"Total banned:\s+(\d+)", out)
        f_val  = failed.group(1) if failed else "?"
        b_val  = banned.group(1) if banned else "?"
        tf_val = t_fail.group(1) if t_fail else "?"
        tb_val = t_ban.group(1)  if t_ban  else "?"
        total_banned += int(b_val) if b_val.isdigit() else 0
        icon = "🔴" if b_val.isdigit() and int(b_val) > 0 else "🟢"
        lines.append(f"{icon} *{jail}*\n   Falhas: `{f_val}` | Banidos: `{b_val}` | Total: `{tf_val}/{tb_val}`")
    lines.append(f"\n🚫 *Total IPs banidos agora: {total_banned}*")
    send(chat_id, "\n".join(lines))


def cmd_banned(chat_id):
    if not is_installed("fail2ban"):
        _fail2ban_not_installed(chat_id)
        return
    jails = get_active_jails()
    if not jails:
        send(chat_id, "⚠️ Nenhum jail ativo no Fail2Ban.")
        return
    lines      = [f"🚫 *IPs Banidos Agora*\n📅 {now()}\n"]
    any_banned = False
    for jail in jails:
        out   = run(f"fail2ban-client status {jail}")
        match = re.search(r"Banned IP list:\s+(.*)", out)
        if match:
            ips = match.group(1).strip().split()
            if ips:
                any_banned = True
                lines.append(f"*{jail}* ({len(ips)}):")
                lines.append("\n".join([f"  `{ip}`" for ip in ips]))
    if not any_banned:
        lines.append("✅ Nenhum IP banido no momento.")
    send(chat_id, "\n".join(lines))


def cmd_unban(chat_id, ip):
    if not is_installed("fail2ban"):
        _fail2ban_not_installed(chat_id)
        return
    if not ip or not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        send(chat_id, "⚠️ Use: `/unban 1.2.3.4`")
        return
    jails    = get_active_jails()
    unbanned = []
    for jail in jails:
        result = run(f"fail2ban-client set {jail} unbanip {ip} 2>&1")
        if "1" in result or "unbanned" in result.lower():
            unbanned.append(jail)
    if unbanned:
        send(chat_id, f"✅ IP `{ip}` desbanido em: `{'`, `'.join(unbanned)}`")
    else:
        send(chat_id, f"ℹ️ IP `{ip}` não estava banido em nenhum jail.")


# ─── Segurança — Menu ──────────────────────────────────────────────────────────

def cmd_seguranca(chat_id):
    buttons = [
        [
            {"text": "🔒 Fail2Ban",   "callback_data": "seg_fail2ban"},
            {"text": "🚫 IPs Banidos", "callback_data": "seg_banned"},
        ],
        [
            {"text": "🔓 Desbanir IP", "callback_data": "seg_unban"},
            {"text": "🛡️ Firewall",   "callback_data": "seg_firewall"},
        ],
        [
            {"text": "🏠 Menu Principal", "callback_data": "cmd_start"},
        ],
    ]
    send_buttons(chat_id,
        "🔒 *Menu de Segurança*\n\n"
        "Escolha uma opção:",
        buttons
    )


# ─── Segurança — Firewall ──────────────────────────────────────────────────────

# Porta aguardando input do usuário: chat_id -> "open" | "close"
_awaiting_port = {}

SSH_PORT = 22  # protegida permanentemente

def cmd_firewall(chat_id):
    status_out = run("ufw status verbose 2>/dev/null")
    is_active  = "Status: active" in status_out

    if is_active:
        # Extrai regras ativas (linhas com ALLOW/DENY)
        rules = []
        for line in status_out.splitlines():
            if re.search(r"ALLOW|DENY|REJECT", line, re.IGNORECASE):
                line = line.strip()
                if line and not line.startswith("To"):
                    rules.append(f"  `{line}`")
        rules_txt = "\n".join(rules) if rules else "  _Nenhuma regra definida_"
        msg = (
            f"🛡️ *Firewall (UFW)*\n📅 {now()}\n\n"
            f"✅ *Status: ATIVO*\n\n"
            f"🔒 *Porta {SSH_PORT} (SSH) — protegida permanentemente*\n\n"
            f"📋 *Regras ativas:*\n{rules_txt}"
        )
        buttons = [
            [{"text": "➕ Abrir porta",  "callback_data": "fw_open_port"},
             {"text": "➖ Fechar porta", "callback_data": "fw_close_port"}],
            [{"text": "🔄 Recarregar regras", "callback_data": "fw_reload"}],
        ]
    else:
        msg = (
            "🛡️ *Firewall (UFW)*\n\n"
            "❌ *Status: INATIVO*\n\n"
            "⚠️ *Ao ativar, o bot irá automaticamente:*\n"
            f"• Liberar porta `{SSH_PORT}/tcp` (SSH) *antes* de ativar\n"
            "• Bloquear todo tráfego de entrada não autorizado\n"
            "• Permitir todo tráfego de saída\n\n"
            f"🔒 A porta {SSH_PORT} *não poderá ser bloqueada* por este bot.\n\n"
            "Deseja ativar o firewall?"
        )
        buttons = [
            [{"text": "✅ Ativar com SSH protegido", "callback_data": "fw_enable"},
             {"text": "❌ Cancelar",                 "callback_data": "install_cancel"}],
        ]
    send_buttons(chat_id, msg, buttons)

def cb_fw_enable(chat_id):
    send(chat_id, f"🔒 Configurando firewall com porta {SSH_PORT} protegida...")
    run("ufw --force reset")
    run("ufw default deny incoming")
    run("ufw default allow outgoing")
    run(f"ufw allow {SSH_PORT}/tcp comment 'SSH protegido'")
    run("ufw --force enable")
    logging.info(f"Firewall ativado por {chat_id}")
    send(chat_id,
        f"✅ *Firewall ativado!*\n\n"
        f"🔒 Porta `{SSH_PORT}/tcp` liberada e protegida.\n"
        "🚫 Todo tráfego de entrada bloqueado por padrão.\n\n"
        "Use /firewall para gerenciar portas."
    )

def cb_fw_open_port(chat_id):
    _awaiting_port[chat_id] = "open"
    send(chat_id,
        "➕ *Abrir porta*\n\n"
        "Digite o número da porta _(ex: `80`, `443`, `3000`)_\n"
        "Ou porta/protocolo _(ex: `8080/tcp`, `53/udp`)_\n\n"
        "_Envie /cancelar para cancelar._"
    )

def cb_fw_close_port(chat_id):
    _awaiting_port[chat_id] = "close"
    send(chat_id,
        "➖ *Fechar porta*\n\n"
        "Digite o número da porta que deseja fechar.\n"
        f"⚠️ A porta `{SSH_PORT}` (SSH) não pode ser fechada.\n\n"
        "_Envie /cancelar para cancelar._"
    )

def handle_port_input(chat_id, text):
    action = _awaiting_port.pop(chat_id)

    if text.strip().lstrip("/").lower() == "cancelar":
        send(chat_id, "❌ Operação cancelada.")
        return

    match = re.match(r"^(\d+)(?:/(tcp|udp))?$", text.strip())
    if not match:
        send(chat_id, "⚠️ Formato inválido. Use `80`, `443` ou `8080/tcp`.")
        return

    port  = int(match.group(1))
    proto = match.group(2) or "tcp"

    if port < 1 or port > 65535:
        send(chat_id, "⚠️ Porta inválida. Use um valor entre 1 e 65535.")
        return

    if action == "close" and port == SSH_PORT:
        send(chat_id, f"🔒 A porta `{SSH_PORT}` (SSH) não pode ser fechada por segurança.")
        return

    if action == "open":
        run(f"ufw allow {port}/{proto}")
        send(chat_id, f"✅ Porta `{port}/{proto}` *aberta* no firewall.")
        logging.info(f"Firewall: porta {port}/{proto} aberta por {chat_id}")
    else:
        run(f"ufw delete allow {port}/{proto}")
        send(chat_id, f"✅ Porta `{port}/{proto}` *fechada* no firewall.")
        logging.info(f"Firewall: porta {port}/{proto} fechada por {chat_id}")


# ─── Manutenção — Menu ─────────────────────────────────────────────────────────

def cmd_manutencao(chat_id):
    buttons = [
        [
            {"text": "📦 Atualizações",  "callback_data": "man_atualizacoes"},
            {"text": "⚙️ Controle",     "callback_data": "man_controle"},
        ],
        [
            {"text": "🔄 Atualizar",     "callback_data": "man_atualizar"},
            {"text": "🔌 Reboot",       "callback_data": "man_reboot"},
        ],
        [
            {"text": "📊 Relatório",     "callback_data": "man_relatorio"},
            {"text": "🏠 Menu Principal", "callback_data": "cmd_start"},
        ],
    ]
    send_buttons(chat_id,
        "⚙️ *Menu de Manutenção*\n\n"
        "Escolha uma opção:",
        buttons
    )


# ─── Manutenção ────────────────────────────────────────────────────────────────

def cmd_docker(chat_id):
    if not is_installed("docker"):
        send(chat_id, "⚠️ *Docker não está instalado.*\n\nUse /instalar para instalar aplicações Docker.")
        return
    info = run("docker info --format '{{.ServerVersion}} | {{.OSType}} | {{.Containers}} containers | {{.Images}} images' 2>/dev/null").strip()
    ps_out = run("docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null").strip()
    if not ps_out:
        ps_out = "(sem containers)"
    if len(ps_out) > 4000:
        ps_out = ps_out[:4000] + "\n..."
    send(chat_id, f"🐳 *Docker*\n📅 {now()}\n\n📋 *Info:* `{info or 'n/d'}`\n\n```\n{ps_out}\n```")


def cmd_erros(chat_id):
    out = run("journalctl -p 3 -n 30 --no-pager 2>/dev/null").strip()
    if not out:
        send(chat_id, f"✅ *Nenhum erro recente no sistema.*\n📅 {now()}")
        return
    if len(out) > 4000:
        out = out[-4000:]
    send(chat_id, f"🚨 *Erros do Sistema*\n📅 {now()}\n\n```\n{out}\n```")


def cmd_atualizacoes(chat_id):
    cache_age = run("stat -c '%Y' /var/cache/apt/pkgcache.bin 2>/dev/null || echo 0").strip()
    age_note = ""
    if cache_age and cache_age.isdigit():
        age_sec = time.time() - int(cache_age)
        if age_sec > 86400:
            age_note = f"\n⚠️ _Cache do apt tem {int(age_sec/86400)} dias. Execute `apt update` para atualizar._"
        elif age_sec > 3600:
            age_note = f"\n📌 _Cache do apt tem {int(age_sec/3600)}h._"

    out = run("apt list --upgradable 2>/dev/null")
    lines = [l for l in out.splitlines() if l.strip() and not l.startswith("Listing") and "WARNING" not in l]

    if not lines:
        send(chat_id, f"✅ *Sistema atualizado!*\n\nNenhum pacote pendente.{age_note}")
        return

    count = len(lines)
    show = lines[:60]
    pkg_list = "\n".join(
        f"  `{l.split('/')[0]}` → {l.split()[-1] if len(l.split()) > 1 else '?'}"
        for l in show
    )
    more = f"\n\n_... e mais {count - 60} pacotes_" if count > 60 else ""

    msg = (
        f"📦 *Pacotes Pendentes de Atualização*\n"
        f"📅 {now()}\n\n"
        f"🔢 *Total: {count} pacotes*{age_note}\n\n"
        f"{pkg_list}{more}\n\n"
        f"_Use /atualizar para instalar._"
    )
    send(chat_id, msg)


def cmd_atualizar(chat_id):
    send_buttons(chat_id,
        "🔄 *Menu de Atualização*\n\n"
        "Escolha o que deseja atualizar:",
        [[
            {"text": "🖥️ Sistema",  "callback_data": "update_sistema_info"},
            {"text": "🤖 Bot",      "callback_data": "update_bot_info"},
        ]]
    )

def cb_update_sistema_info(chat_id):
    send_buttons(chat_id,
        "🔄 *Atualizar Sistema*\n\n"
        "Isso vai executar:\n"
        "`apt-get update && apt-get upgrade -y`\n\n"
        "⚠️ *Atenção:*\n"
        "• Pode levar alguns minutos dependendo dos pacotes\n"
        "• O servidor continuará online durante a atualização\n"
        "• Você será notificado quando concluir\n\n"
        "Confirma a atualização?",
        [[
            {"text": "✅ Sim, atualizar", "callback_data": "update_sistema_go"},
            {"text": "❌ Cancelar",       "callback_data": "install_cancel"},
        ]]
    )

def _run_atualizar_sistema(chat_id):
    logging.info(f"Iniciando atualização do sistema (chat_id={chat_id})")
    try:
        send(chat_id, "⏳ *Executando `apt-get update`...*")
        subprocess.run("apt-get update", shell=True, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)

        send(chat_id, "⏳ *Executando `apt-get upgrade -y`...*")
        r2 = subprocess.run("DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
                            shell=True, capture_output=True, text=True, timeout=1800, stdin=subprocess.DEVNULL)

        if r2.returncode == 0:
            upgraded = len(re.findall(r"^Unpacking|^Setting up", r2.stdout, re.MULTILINE))
            msg = f"✅ *Sistema atualizado com sucesso!*\n\n📦 Pacotes processados: `{upgraded}`\n\n"
            reboot_needed = run("[ -f /var/run/reboot-required ] && echo yes || echo no").strip()
            msg += "⚠️ _Reinicialização recomendada. Use /reboot quando possível._" if reboot_needed == "yes" else "_Nenhum reboot necessário._"
            send(chat_id, msg)
        else:
            erro = (r2.stderr or r2.stdout or "Sem detalhes.")[-1500:]
            send(chat_id, f"❌ *Erro na atualização*\n\n```\n{erro}\n```")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A atualização excedeu o tempo limite.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro na atualização: {e}")

_reboot_pending = {}

def cb_update_bot_info(chat_id):
    repo_dir = cfg.get("repo_dir", "/opt/woncloud-bot")
    send_buttons(chat_id,
        "🤖 *Atualizar Bot*\n\n"
        "Isso vai executar:\n"
        f"`cd {repo_dir} && git pull && sudo bash install.sh --no-restart`\n\n"
        "⚠️ *Atenção:*\n"
        "• O bot será atualizado com a versão mais recente\n"
        "• O serviço será reiniciado após confirmação\n"
        "• Pode levar alguns minutos\n"
        "• Você será notificado quando concluir\n\n"
        "Confirma a atualização do bot?",
        [[
            {"text": "✅ Sim, atualizar", "callback_data": "update_bot_go"},
            {"text": "❌ Cancelar",       "callback_data": "install_cancel"},
        ]]
    )

def _run_atualizar_bot(chat_id):
    logging.info(f"Iniciando atualização do bot (chat_id={chat_id})")
    repo_dir = cfg.get("repo_dir", "/opt/woncloud-bot")
    try:
        send(chat_id, "⏳ *Atualizando repositório...*")
        r1 = subprocess.run(f"cd {repo_dir} && git pull",
                            shell=True, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)

        if "Already up to date" in r1.stdout or r1.returncode == 0:
            send(chat_id, "⏳ *Instalando atualização...*")
            r2 = subprocess.run(f"cd {repo_dir} && sudo -n bash install.sh --no-restart",
                                shell=True, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)

            if r2.returncode == 0:
                send(chat_id, "✅ *Bot atualizado com sucesso!*\n\n🔄 O serviço será reiniciado em 3 segundos...")
                logging.info(f"Bot atualizado com sucesso (chat_id={chat_id})")
                time.sleep(3)
                subprocess.Popen("systemctl restart woncloud-bot", shell=True)
            else:
                erro = (r2.stderr or r2.stdout or "Sem detalhes.")[-1500:]
                send(chat_id, f"❌ *Erro na instalação*\n\n```\n{erro}\n```")
        else:
            erro = (r1.stderr or r1.stdout or "Sem detalhes.")[-1500:]
            send(chat_id, f"❌ *Erro ao atualizar repositório*\n\n```\n{erro}\n```")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A atualização excedeu o tempo limite.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro na atualização do bot: {e}")

def _run_relatorio(chat_id):
    logging.info(f"Executando relatório manual (chat_id={chat_id})")
    try:
        report_path = os.path.join(BASE_DIR, "report.py")
        python = os.path.join(BASE_DIR, "venv", "bin", "python3")
        r = subprocess.run([python, report_path], capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            send(chat_id, r.stdout.strip())
        elif r.stderr.strip():
            send(chat_id, f"❌ *Erro ao gerar relatório:*\n```\n{r.stderr.strip()[-1500:]}\n```")
        else:
            send(chat_id, "⚠️ Relatório gerado sem saída.")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — o relatório demorou mais de 60 segundos.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")

def cmd_relatorio(chat_id):
    send(chat_id, "⏳ *Gerando relatório do servidor...*")
    threading.Thread(target=_run_relatorio, args=(chat_id,), daemon=True).start()

def cmd_reboot(chat_id):
    _reboot_pending[chat_id] = time.time()
    send(chat_id,
        "⚠️ *Confirma o reboot do servidor?*\n\n"
        "Digite /confirmarreboot para confirmar.\n"
        "_Esta confirmação expira em 60 segundos._"
    )

def cmd_confirmar_reboot(chat_id):
    ts = _reboot_pending.get(chat_id)
    if not ts or (time.time() - ts) > 60:
        _reboot_pending.pop(chat_id, None)
        send(chat_id, "❌ Confirmação expirada ou não solicitada. Use /reboot novamente.")
        return
    _reboot_pending.pop(chat_id, None)
    send(chat_id, "🔄 *Reiniciando o servidor agora...*\n_O bot voltará automaticamente após o boot._")
    logging.info(f"Reboot autorizado pelo chat_id {chat_id}")
    time.sleep(2)
    subprocess.Popen("shutdown -r now", shell=True)


# ─── Instalações ───────────────────────────────────────────────────────────────

def cmd_instalar(chat_id):
    f2b_label = "🔒 Fail2Ban ✅" if is_installed("fail2ban") else "🔒 Fail2Ban"
    buttons = [
        [{"text": "⭐ Won Code",             "callback_data": "install_woncode_info"}],
        [{"text": "🛠️ aaPanel",             "callback_data": "install_aapanel_info"}],
        [{"text": "🛠️ aaPanel + OpenClaw",  "callback_data": "install_aaclaw_info"}],
        [{"text": "☁️ CloudPanel",           "callback_data": "install_cloudpanel_info"}],
        [{"text": "🚀 Coolify",             "callback_data": "install_coolify_info"}],
        [{"text": "🐳 EasyPanel",           "callback_data": "install_easypanel_info"}],
        [{"text": f2b_label,                "callback_data": "install_fail2ban_info"}],
        [{"text": "🦅 OpenClaw",            "callback_data": "install_openclaw_info"}],
    ]
    send_buttons(chat_id,
        "📦 *Menu de Instalação*\n\n"
        "Escolha a aplicação que deseja instalar no servidor:",
        buttons
    )

def cb_easypanel_info(chat_id):
    msg = (
        "🐳 *EasyPanel — Painel Docker*\n\n"
        "EasyPanel é um painel de controle para deploy e gerenciamento de "
        "aplicações em containers Docker, com suporte a Let's Encrypt, "
        "banco de dados, deploys automáticos e muito mais.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *O que será instalado:*\n"
        "• Docker Engine (se não instalado)\n"
        "• EasyPanel e todos os seus containers\n"
        "• Interface web na porta `3000`\n\n"
        "⚠️ *Atenção — leia antes de confirmar:*\n"
        "• ⏱ A instalação pode levar *10 a 30 minutos*\n"
        "• 📦 É uma aplicação *Docker pesada* (múltiplos containers)\n"
        "• 🌐 Requer internet estável durante todo o processo\n"
        "• 💾 Consome espaço em disco considerável\n"
        "• 📲 Você será notificado aqui quando concluir\n\n"
        "Deseja prosseguir com a instalação?"
    )
    buttons = [[
        {"text": "✅ Sim, instalar agora", "callback_data": "install_easypanel_go"},
        {"text": "❌ Cancelar",            "callback_data": "install_cancel"},
    ]]
    send_buttons(chat_id, msg, buttons)

def _run_easypanel_install(chat_id):
    logging.info(f"Iniciando instalação do EasyPanel (chat_id={chat_id})")
    try:
        result = subprocess.run(
            "curl -sSL https://get.easypanel.io | sh",
            shell=True, capture_output=True, text=True, timeout=2700
        )
        if result.returncode == 0:
            send(chat_id,
                "✅ *EasyPanel instalado com sucesso!*\n\n"
                "Acesse o painel pelo navegador:\n"
                "`http://<IP-do-servidor>:3000`\n\n"
                "Na primeira vez, crie seu usuário administrador.\n\n"
                "_Dica: configure um domínio e SSL diretamente no painel._"
            )
            logging.info("EasyPanel instalado com sucesso.")
        else:
            erro = (result.stderr or result.stdout or "Sem detalhes.")[-2000:]
            send(chat_id, f"❌ *Erro na instalação do EasyPanel*\n\nCódigo: `{result.returncode}`\n\n```\n{erro}\n```")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A instalação excedeu 45 minutos e foi interrompida.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro EasyPanel: {e}")

def cb_easypanel_go(chat_id):
    send(chat_id,
        "⏳ *Instalação do EasyPanel iniciada!*\n\n"
        "A instalação está rodando em segundo plano.\n"
        "Você receberá uma mensagem aqui quando terminar.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 *Próximos passos após instalação:*\n"
        "1. Acesse `http://<IP>:3000` no navegador\n"
        "2. Crie seu usuário administrador\n"
        "3. Configure domínio e SSL no painel\n\n"
        "_Este processo pode levar 10 a 30 minutos..._"
    )
    threading.Thread(target=_run_easypanel_install, args=(chat_id,), daemon=True).start()

def cb_coolify_info(chat_id):
    msg = (
        "🚀 *Coolify — Plataforma self-hosted*\n\n"
        "Coolify é uma alternativa self-hosted ao Heroku/Netlify/Vercel. "
        "Permite fazer deploy de aplicações, bancos de dados e serviços "
        "com interface web, SSL automático e suporte a Git.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *O que será instalado:*\n"
        "• Docker Engine (se não instalado)\n"
        "• Coolify e seus serviços\n"
        "• Interface web na porta `8000`\n\n"
        "⚠️ *Atenção — leia antes de confirmar:*\n"
        "• ⏱ A instalação pode levar *10 a 20 minutos*\n"
        "• 📦 Aplicação *Docker pesada* (múltiplos containers)\n"
        "• 🌐 Requer internet estável durante o processo\n"
        "• 💾 Requer ao menos *2GB de RAM* e *30GB de disco*\n"
        "• 📲 Você será notificado aqui quando concluir\n\n"
        "Deseja prosseguir com a instalação?"
    )
    buttons = [[
        {"text": "✅ Sim, instalar agora", "callback_data": "install_coolify_go"},
        {"text": "❌ Cancelar",            "callback_data": "install_cancel"},
    ]]
    send_buttons(chat_id, msg, buttons)

def _run_coolify_install(chat_id):
    logging.info(f"Iniciando instalação do Coolify (chat_id={chat_id})")
    try:
        result = subprocess.run(
            "curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash",
            shell=True, capture_output=True, text=True, timeout=2700
        )
        if result.returncode == 0:
            send(chat_id,
                "✅ *Coolify instalado com sucesso!*\n\n"
                "Acesse o painel pelo navegador:\n"
                "`http://<IP-do-servidor>:8000`\n\n"
                "Na primeira vez, crie sua conta de administrador.\n\n"
                "_Dica: configure um domínio e SSL nas configurações do painel._"
            )
            logging.info("Coolify instalado com sucesso.")
        else:
            erro = (result.stderr or result.stdout or "Sem detalhes.")[-2000:]
            send(chat_id, f"❌ *Erro na instalação do Coolify*\n\nCódigo: `{result.returncode}`\n\n```\n{erro}\n```")
            logging.error(f"Erro Coolify (código {result.returncode}): {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A instalação excedeu 45 minutos e foi interrompida.")
        logging.error("Timeout na instalação do Coolify")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro inesperado Coolify: {e}")

def cb_coolify_go(chat_id):
    send(chat_id,
        "⏳ *Instalação do Coolify iniciada!*\n\n"
        "A instalação está rodando em segundo plano.\n"
        "Você receberá uma mensagem aqui quando terminar.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 *Próximos passos após instalação:*\n"
        "1. Acesse `http://<IP>:8000` no navegador\n"
        "2. Crie sua conta de administrador\n"
        "3. Configure domínio e SSL no painel\n\n"
        "_Este processo pode levar 10 a 20 minutos..._"
    )
    threading.Thread(target=_run_coolify_install, args=(chat_id,), daemon=True).start()


def cb_aapanel_info(chat_id):
    msg = (
        "🛠️ *aaPanel — Painel de Hospedagem*\n\n"
        "aaPanel é um painel de controle de servidor web completo, "
        "com gerenciamento de sites, banco de dados, FTP, SSL, "
        "agendamentos e monitoramento — tudo via interface web.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *O que será instalado:*\n"
        "• Nginx ou Apache (à sua escolha no painel)\n"
        "• PHP, MySQL, FTP, Redis (opcionais via painel)\n"
        "• Interface web na porta `7800` com SSL\n\n"
        "⚠️ *Atenção — leia antes de confirmar:*\n"
        "• ⏱ A instalação pode levar *5 a 15 minutos*\n"
        "• 🌐 Requer internet estável durante o processo\n"
        "• 💾 Requer ao menos *1GB de RAM* e *10GB de disco*\n"
        "• 🔒 A instalação usa o parâmetro `ipssl` (acesso via IP + SSL)\n"
        "• 📲 Você será notificado aqui quando concluir\n\n"
        "Deseja prosseguir com a instalação?"
    )
    buttons = [[
        {"text": "✅ Sim, instalar agora", "callback_data": "install_aapanel_go"},
        {"text": "❌ Cancelar",            "callback_data": "install_cancel"},
    ]]
    send_buttons(chat_id, msg, buttons)

def _run_aapanel_install(chat_id):
    logging.info(f"Iniciando instalação do aaPanel (chat_id={chat_id})")
    try:
        cmd = (
            "URL=https://www.aapanel.com/script/install_panel_en.sh && "
            "if [ -f /usr/bin/curl ]; then curl -ksSO $URL; "
            "else wget --no-check-certificate -O install_panel_en.sh $URL; fi && "
            "bash install_panel_en.sh ipssl"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1800)
        if result.returncode == 0:
            # Extrai credenciais do output se disponíveis
            out = result.stdout
            creds = ""
            for line in out.splitlines():
                if any(k in line.lower() for k in ["address", "username", "password", "panel", "http"]):
                    creds += f"  `{line.strip()}`\n"
            send(chat_id,
                "✅ *aaPanel instalado com sucesso!*\n\n"
                + (f"📋 *Credenciais de acesso:*\n{creds}\n" if creds else
                   "Acesse o painel pelo navegador:\n`https://<IP>:7800`\n\n") +
                "_As credenciais iniciais também ficam em `/www/server/panel/default.pl`_"
            )
            logging.info("aaPanel instalado com sucesso.")
        else:
            erro = (result.stderr or result.stdout or "Sem detalhes.")[-2000:]
            send(chat_id, f"❌ *Erro na instalação do aaPanel*\n\nCódigo: `{result.returncode}`\n\n```\n{erro}\n```")
            logging.error(f"Erro aaPanel (código {result.returncode}): {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A instalação excedeu 30 minutos e foi interrompida.")
        logging.error("Timeout na instalação do aaPanel")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro inesperado aaPanel: {e}")

def cb_aapanel_go(chat_id):
    send(chat_id,
        "⏳ *Instalação do aaPanel iniciada!*\n\n"
        "A instalação está rodando em segundo plano.\n"
        "Você receberá uma mensagem aqui quando terminar.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 *Próximos passos após instalação:*\n"
        "1. Acesse `https://<IP>:7800` no navegador\n"
        "2. Use as credenciais exibidas ao concluir\n"
        "3. Configure sites e serviços pelo painel\n\n"
        "_Este processo pode levar 5 a 15 minutos..._"
    )
    threading.Thread(target=_run_aapanel_install, args=(chat_id,), daemon=True).start()


def cb_aaclaw_info(chat_id):
    msg = (
        "🛠️ *aaPanel Free + OpenClaw*\n\n"
        "Versão do aaPanel com o plugin OpenClaw integrado, "
        "voltado para gerenciamento avançado de hospedagem com "
        "recursos extras de segurança e performance.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *O que será instalado:*\n"
        "• aaPanel Free\n"
        "• Plugin OpenClaw (chave `9e7f1eae`)\n"
        "• Interface web na porta `7800` com SSL\n\n"
        "⚠️ *Atenção — leia antes de confirmar:*\n"
        "• ⏱ A instalação pode levar *5 a 15 minutos*\n"
        "• 🌐 Requer internet estável durante o processo\n"
        "• 💾 Requer ao menos *1GB de RAM* e *10GB de disco*\n"
        "• 📲 Você será notificado aqui quando concluir\n\n"
        "Deseja prosseguir com a instalação?"
    )
    buttons = [[
        {"text": "✅ Sim, instalar agora", "callback_data": "install_aaclaw_go"},
        {"text": "❌ Cancelar",            "callback_data": "install_cancel"},
    ]]
    send_buttons(chat_id, msg, buttons)

def _run_aaclaw_install(chat_id):
    logging.info(f"Iniciando instalação do aaPanel + OpenClaw (chat_id={chat_id})")
    try:
        cmd = (
            "URL=https://www.aapanel.com/script/aaClaw.sh && "
            "if [ -f /usr/bin/curl ]; then curl -ksSO $URL; "
            "else wget --no-check-certificate -O aaClaw.sh $URL; fi && "
            "bash aaClaw.sh 9e7f1eae"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1800)
        if result.returncode == 0:
            out   = result.stdout
            creds = ""
            for line in out.splitlines():
                if any(k in line.lower() for k in ["address", "username", "password", "panel", "http"]):
                    creds += f"  `{line.strip()}`\n"
            send(chat_id,
                "✅ *aaPanel + OpenClaw instalado com sucesso!*\n\n"
                + (f"📋 *Credenciais de acesso:*\n{creds}\n" if creds else
                   "Acesse o painel pelo navegador:\n`https://<IP>:7800`\n\n") +
                "_As credenciais também ficam em `/www/server/panel/default.pl`_"
            )
            logging.info("aaPanel + OpenClaw instalado com sucesso.")
        else:
            erro = (result.stderr or result.stdout or "Sem detalhes.")[-2000:]
            send(chat_id, f"❌ *Erro na instalação do aaPanel + OpenClaw*\n\nCódigo: `{result.returncode}`\n\n```\n{erro}\n```")
            logging.error(f"Erro aaClaw (código {result.returncode}): {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A instalação excedeu 30 minutos e foi interrompida.")
        logging.error("Timeout na instalação do aaPanel + OpenClaw")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro inesperado aaClaw: {e}")

def cb_aaclaw_go(chat_id):
    send(chat_id,
        "⏳ *Instalação do aaPanel + OpenClaw iniciada!*\n\n"
        "A instalação está rodando em segundo plano.\n"
        "Você receberá uma mensagem aqui quando terminar.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 *Próximos passos após instalação:*\n"
        "1. Acesse `https://<IP>:7800` no navegador\n"
        "2. Use as credenciais exibidas ao concluir\n"
        "3. Configure sites e serviços pelo painel\n\n"
        "_Este processo pode levar 5 a 15 minutos..._"
    )
    threading.Thread(target=_run_aaclaw_install, args=(chat_id,), daemon=True).start()


CLOUDPANEL_HASH = "19cfa702e7936a79e47812ff57d9859175ea902c62a68b2c15ccd1ebaf36caeb"
CLOUDPANEL_ENGINES = {
    "MYSQL_8.4":     "MySQL 8.4",
    "MYSQL_8.0":     "MySQL 8.0",
    "MARIADB_11.4":  "MariaDB 11.4",
    "MARIADB_10.11": "MariaDB 10.11",
}

def cb_cloudpanel_info(chat_id):
    msg = (
        "☁️ *CloudPanel — Painel de Hospedagem*\n\n"
        "CloudPanel é um painel moderno, leve e gratuito para gerenciar "
        "servidores web com suporte a PHP, Node.js, Python, MySQL, MariaDB, "
        "SSL automático e muito mais.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *O que será instalado:*\n"
        "• CloudPanel CE v2\n"
        "• Banco de dados à sua escolha\n"
        "• Interface web na porta `8443` (HTTPS)\n\n"
        "⚠️ *Atenção:*\n"
        "• ⏱ Instalação pode levar *10 a 20 minutos*\n"
        "• 💾 Requer ao menos *1GB de RAM* e *15GB de disco*\n"
        "• 📲 Você será notificado quando concluir\n\n"
        "Escolha o banco de dados:"
    )
    buttons = [
        [{"text": "🐬 MySQL 8.4  (recomendado)", "callback_data": "cp_go_MYSQL_8.4"}],
        [{"text": "🐬 MySQL 8.0",                "callback_data": "cp_go_MYSQL_8.0"}],
        [{"text": "🦭 MariaDB 11.4",             "callback_data": "cp_go_MARIADB_11.4"}],
        [{"text": "🦭 MariaDB 10.11",            "callback_data": "cp_go_MARIADB_10.11"}],
        [{"text": "❌ Cancelar",                  "callback_data": "install_cancel"}],
    ]
    send_buttons(chat_id, msg, buttons)

def cb_cloudpanel_confirm(chat_id, engine):
    label = CLOUDPANEL_ENGINES.get(engine, engine)
    msg = (
        f"☁️ *CloudPanel + {label}*\n\n"
        f"Confirma a instalação com *{label}* como banco de dados?\n\n"
        "O processo irá:\n"
        "• Atualizar o sistema (`apt upgrade`)\n"
        "• Baixar e verificar o instalador (sha256)\n"
        f"• Instalar CloudPanel com `DB_ENGINE={engine}`\n\n"
        "_Este processo pode levar 10 a 20 minutos._"
    )
    buttons = [[
        {"text": f"✅ Confirmar",  "callback_data": f"cp_confirm_{engine}"},
        {"text": "◀️ Voltar",     "callback_data": "install_cloudpanel_info"},
    ]]
    send_buttons(chat_id, msg, buttons)

def _run_cloudpanel_install(chat_id, engine):
    logging.info(f"Iniciando instalação do CloudPanel engine={engine} (chat_id={chat_id})")
    try:
        send(chat_id, "⏳ *Atualizando sistema...*")
        subprocess.run(
            "apt update && apt -y upgrade && apt -y install curl wget sudo",
            shell=True, capture_output=True, text=True, timeout=600
        )
        send(chat_id, "⏳ *Baixando e verificando instalador...*")
        dl = subprocess.run(
            "curl -sS https://installer.cloudpanel.io/ce/v2/install.sh -o /tmp/cp_install.sh",
            shell=True, capture_output=True, text=True, timeout=60
        )
        verify = subprocess.run(
            f'echo "{CLOUDPANEL_HASH} /tmp/cp_install.sh" | sha256sum -c',
            shell=True, capture_output=True, text=True, timeout=10
        )
        if verify.returncode != 0:
            send(chat_id, "❌ *Falha na verificação do instalador (sha256 inválido).*\nAbortando por segurança.")
            logging.error("CloudPanel: sha256 inválido")
            return

        label = CLOUDPANEL_ENGINES.get(engine, engine)
        send(chat_id, f"⏳ *Instalando CloudPanel com {label}...*")
        result = subprocess.run(
            f"CLOUD=hetzner DB_ENGINE={engine} bash /tmp/cp_install.sh",
            shell=True, capture_output=True, text=True, timeout=1800
        )
        if result.returncode == 0:
            send(chat_id,
                f"✅ *CloudPanel + {label} instalado com sucesso!*\n\n"
                "Acesse o painel pelo navegador:\n"
                "`https://<IP>:8443`\n\n"
                "Na primeira vez, crie seu usuário administrador.\n\n"
                "_Dica: configure seu domínio e SSL pelo painel._"
            )
            logging.info(f"CloudPanel ({engine}) instalado com sucesso.")
        else:
            erro = (result.stderr or result.stdout or "Sem detalhes.")[-2000:]
            send(chat_id, f"❌ *Erro na instalação do CloudPanel*\n\nCódigo: `{result.returncode}`\n\n```\n{erro}\n```")
            logging.error(f"Erro CloudPanel ({engine}): {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A instalação excedeu o tempo limite e foi interrompida.")
        logging.error(f"Timeout CloudPanel ({engine})")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro inesperado CloudPanel: {e}")

def cb_cloudpanel_go(chat_id, engine):
    label = CLOUDPANEL_ENGINES.get(engine, engine)
    send(chat_id,
        f"⏳ *Instalação do CloudPanel + {label} iniciada!*\n\n"
        "A instalação está rodando em segundo plano.\n"
        "Você receberá uma mensagem aqui quando terminar.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 *Próximos passos após instalação:*\n"
        "1. Acesse `https://<IP>:8443` no navegador\n"
        "2. Crie seu usuário administrador\n"
        "3. Configure domínio e SSL pelo painel\n\n"
        "_Este processo pode levar 10 a 20 minutos..._"
    )
    threading.Thread(target=_run_cloudpanel_install, args=(chat_id, engine), daemon=True).start()


OPENCLAW_METHODS = {
    "quickstart": ("🚀 Quick Start",  "curl -fsSL https://openclaw.ai/install.sh | bash"),
    "npm":        ("📦 npm",          "npm i -g openclaw && openclaw onboard"),
    "hackable":   ("🔧 Hackable (git)","curl -fsSL https://openclaw.ai/install.sh | bash -s -- --install-method git"),
}

def cb_openclaw_info(chat_id):
    msg = (
        "🦅 *OpenClaw — Agente de IA no terminal*\n\n"
        "OpenClaw é um agente de IA que roda direto no terminal, "
        "permitindo automatizar tarefas, gerar código e interagir "
        "com o servidor via linguagem natural.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *Atenção:*\n"
        "• Requer Node.js instalado (para método npm)\n"
        "• Instalação rápida (~1 a 3 minutos)\n"
        "• 📲 Você será notificado quando concluir\n\n"
        "Escolha o método de instalação:"
    )
    buttons = [
        [{"text": "🚀 Quick Start",   "callback_data": "openclaw_go_quickstart"}],
        [{"text": "📦 npm",           "callback_data": "openclaw_go_npm"}],
        [{"text": "🔧 Hackable (git)","callback_data": "openclaw_go_hackable"}],
        [{"text": "❌ Cancelar",       "callback_data": "install_cancel"}],
    ]
    send_buttons(chat_id, msg, buttons)

def _run_openclaw_install(chat_id, method):
    label, cmd = OPENCLAW_METHODS[method]
    logging.info(f"Instalando OpenClaw método={method} (chat_id={chat_id})")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            extra = "\nRode `openclaw onboard` no terminal para configurar." if method == "npm" else ""
            send(chat_id,
                f"✅ *OpenClaw instalado com sucesso! ({label})*\n\n"
                f"Use no terminal:\n`openclaw`\n{extra}"
            )
            logging.info(f"OpenClaw ({method}) instalado com sucesso.")
        else:
            erro = (result.stderr or result.stdout or "Sem detalhes.")[-1500:]
            send(chat_id, f"❌ *Erro na instalação do OpenClaw*\n\nCódigo: `{result.returncode}`\n\n```\n{erro}\n```")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A instalação demorou mais de 5 minutos.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro OpenClaw: {e}")

def cb_openclaw_go(chat_id, method):
    label, _ = OPENCLAW_METHODS.get(method, ("?", ""))
    send(chat_id,
        f"⏳ *Instalando OpenClaw ({label})...*\n\n"
        "Aguarde, isso leva cerca de 1 a 3 minutos.\n"
        "Você será notificado ao concluir."
    )
    threading.Thread(target=_run_openclaw_install, args=(chat_id, method), daemon=True).start()


def cb_woncode_info(chat_id):
    msg = (
        "💻 *Won Code — Agente de Programação Autônomo*\n\n"
        "Won Code gera código, refatora, analisa segurança, "
        "gerencia infraestrutura e automatiza rotinas — tudo via CLI "
        "com roteamento inteligente de LLMs (Gemini, OpenAI, etc).\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *Passos após instalação:*\n"
        "1. `won activate` — ativar licença\n"
        "2. `won setup` — configurar chaves de IA\n"
        "3. `won` — usar o agente\n\n"
        "♾️ _Atualizações vitalícias inclusas._\n"
        "_Para atualizar, rode o mesmo comando de instalação._\n\n"
        "⚠️ *Atenção:*\n"
        "• Instalação rápida (~1 a 2 minutos)\n"
        "• Requer licença para ativar\n"
        "• 📲 Você será notificado quando concluir\n\n"
        "Deseja instalar o Won Code?"
    )
    buttons = [[
        {"text": "✅ Sim, instalar agora", "callback_data": "install_woncode_go"},
        {"text": "❌ Cancelar",            "callback_data": "install_cancel"},
    ]]
    send_buttons(chat_id, msg, buttons)

def _run_woncode_install(chat_id):
    logging.info(f"Instalando Won Code (chat_id={chat_id})")
    try:
        result = subprocess.run(
            "curl -sSL https://install.woncode.com.br | sh",
            shell=True, capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            send(chat_id,
                "✅ *Won Code instalado com sucesso!*\n\n"
                "📋 *Próximos passos no terminal:*\n\n"
                "1️⃣ Ativar licença:\n`won activate`\n\n"
                "2️⃣ Configurar chaves de IA:\n`won setup`\n\n"
                "3️⃣ Usar o agente:\n`won`\n\n"
                "♾️ _Para atualizar, rode novamente o comando de instalação._"
            )
            logging.info("Won Code instalado com sucesso.")
        else:
            erro = (result.stderr or result.stdout or "Sem detalhes.")[-1500:]
            send(chat_id, f"❌ *Erro na instalação do Won Code*\n\nCódigo: `{result.returncode}`\n\n```\n{erro}\n```")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A instalação demorou mais de 5 minutos.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro Won Code: {e}")

def cb_woncode_go(chat_id):
    send(chat_id,
        "⏳ *Instalando Won Code...*\n\n"
        "Aguarde, isso leva cerca de 1 a 2 minutos.\n"
        "Você será notificado ao concluir."
    )
    threading.Thread(target=_run_woncode_install, args=(chat_id,), daemon=True).start()


def cb_fail2ban_info(chat_id):
    if is_installed("fail2ban"):
        send(chat_id,
            "✅ *Fail2Ban já está instalado!*\n\n"
            "Comandos disponíveis:\n\n"
            "🔒 /fail2ban — Relatório completo por jail\n"
            "🚫 /banned — Lista de IPs banidos agora\n"
            "🔓 /unban `<ip>` — Desbanir um IP específico"
        )
        return
    msg = (
        "🔒 *Fail2Ban — Proteção contra ataques*\n\n"
        "Fail2Ban monitora logs do sistema e bane automaticamente "
        "IPs com tentativas de acesso malicioso.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *O que será instalado:*\n"
        "• Fail2Ban via `apt-get`\n"
        "• Habilitado e iniciado como serviço\n\n"
        "⚠️ *Atenção:*\n"
        "• ⏱ Instalação rápida (~1 a 2 minutos)\n"
        "• 🔧 Configuração padrão (jails básicos ativos)\n"
        "• 📲 Você será notificado quando concluir\n\n"
        "Deseja instalar o Fail2Ban agora?"
    )
    buttons = [[
        {"text": "✅ Sim, instalar",  "callback_data": "install_fail2ban_go"},
        {"text": "❌ Cancelar",       "callback_data": "install_cancel"},
    ]]
    send_buttons(chat_id, msg, buttons)

def _run_fail2ban_install(chat_id):
    logging.info(f"Iniciando instalação do Fail2Ban (chat_id={chat_id})")
    try:
        result = subprocess.run(
            "apt-get update -qq && apt-get install -y fail2ban",
            shell=True, capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            subprocess.run("systemctl enable fail2ban && systemctl start fail2ban", shell=True, timeout=15)
            send(chat_id,
                "✅ *Fail2Ban instalado e ativo!*\n\n"
                "O serviço já está rodando e protegendo o servidor.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📋 *Recursos agora disponíveis:*\n\n"
                "🔒 /fail2ban — Relatório completo por jail\n"
                "🚫 /banned — Lista de IPs banidos agora\n"
                "🔓 /unban `<ip>` — Desbanir um IP\n"
                "  _Ex: `/unban 123.456.789.0`_"
            )
            logging.info("Fail2Ban instalado com sucesso.")
        else:
            erro = (result.stderr or result.stdout or "Sem detalhes.")[-1500:]
            send(chat_id, f"❌ *Erro na instalação do Fail2Ban*\n\n```\n{erro}\n```")
    except subprocess.TimeoutExpired:
        send(chat_id, "⏱️ *Timeout* — A instalação demorou mais de 5 minutos e foi cancelada.")
    except Exception as e:
        send(chat_id, f"❌ *Erro inesperado:* `{e}`")
        logging.error(f"Erro Fail2Ban: {e}")

def cb_fail2ban_go(chat_id):
    send(chat_id,
        "⏳ *Instalando Fail2Ban...*\n\n"
        "Aguarde, isso leva aproximadamente 1 a 2 minutos.\n"
        "Você receberá uma notificação ao concluir."
    )
    threading.Thread(target=_run_fail2ban_install, args=(chat_id,), daemon=True).start()


# ─── Callback handler ──────────────────────────────────────────────────────────

def handle_callback(callback):
    chat_id = callback["message"]["chat"]["id"]
    data    = callback.get("data", "")
    cb_id   = callback["id"]

    if AUTHORIZED_CHAT_ID and chat_id != AUTHORIZED_CHAT_ID:
        answer_callback(cb_id, "Acesso negado.")
        return

    answer_callback(cb_id)
    logging.info(f"Callback: {data} de {chat_id}")

    if   data == "seg_fail2ban":            cmd_fail2ban(chat_id)
    elif data == "seg_banned":              cmd_banned(chat_id)
    elif data == "seg_unban":
        send(chat_id,
            "🔓 *Desbanir IP*\n\n"
            "Use o comando:\n"
            "`/unban <ip>`\n\n"
            "_Exemplo: `/unban 192.168.1.100`_"
        )
    elif data == "seg_firewall":            cmd_firewall(chat_id)
    elif data == "mon_status":              cmd_status(chat_id)
    elif data == "mon_servicos":            cmd_servicos(chat_id)
    elif data == "mon_processos":           cmd_processos(chat_id)
    elif data == "mon_rede":                cmd_rede(chat_id)
    elif data == "mon_ping":
        send(chat_id,
            "📡 *Ping & Rota*\n\n"
            "Use o comando:\n"
            "`/ping <host>`\n\n"
            "_Exemplo: `/ping google.com` ou `/ping 8.8.8.8`_"
        )
    elif data == "mon_dns":
        send(chat_id,
            "🔍 *Consulta DNS*\n\n"
            "Use o comando:\n"
            "`/dns <dominio>`\n\n"
            "_Exemplo: `/dns google.com`_"
        )
    elif data == "mon_disco":               cmd_disco(chat_id)
    elif data == "mon_logs":                cmd_logs(chat_id)
    elif data == "mon_erros":               cmd_erros(chat_id)
    elif data == "mon_docker":              cmd_docker(chat_id)
    elif data == "man_atualizacoes":        cmd_atualizacoes(chat_id)
    elif data == "man_controle":            cmd_controle_servicos(chat_id)
    elif data == "man_atualizar":           cmd_atualizar(chat_id)
    elif data == "man_reboot":              cmd_reboot(chat_id)
    elif data == "man_relatorio":          cmd_relatorio(chat_id)
    elif data == "menu_monitoramento":      cmd_monitoramento(chat_id)
    elif data == "menu_seguranca":          cmd_seguranca(chat_id)
    elif data == "menu_instalar":           cmd_instalar(chat_id)
    elif data == "menu_manutencao":         cmd_manutencao(chat_id)
    elif data == "cmd_start":               cmd_start(chat_id, {})
    elif data == "logs_auth":               cb_logs(chat_id, "auth")
    elif data == "logs_syslog":             cb_logs(chat_id, "syslog")
    elif data == "logs_dmesg":              cb_logs(chat_id, "dmesg")
    elif data == "fw_enable":               cb_fw_enable(chat_id)
    elif data == "fw_open_port":            cb_fw_open_port(chat_id)
    elif data == "fw_close_port":           cb_fw_close_port(chat_id)
    elif data == "fw_reload":               run("ufw reload") ; send(chat_id, "🔄 Regras do firewall recarregadas.")
    elif data == "update_sistema_info":     cb_update_sistema_info(chat_id)
    elif data == "update_sistema_go":
        send(chat_id, "⏳ *Atualização iniciada em background.*\nVocê será notificado ao concluir.")
        threading.Thread(target=_run_atualizar_sistema, args=(chat_id,), daemon=True).start()
    elif data == "update_bot_info":         cb_update_bot_info(chat_id)
    elif data == "update_bot_go":
        send(chat_id, "⏳ *Atualização iniciada em background.*\nVocê será notificado ao concluir.")
        threading.Thread(target=_run_atualizar_bot, args=(chat_id,), daemon=True).start()
    elif data == "install_easypanel_info":  cb_easypanel_info(chat_id)
    elif data == "install_easypanel_go":    cb_easypanel_go(chat_id)
    elif data == "install_coolify_info":    cb_coolify_info(chat_id)
    elif data == "install_coolify_go":      cb_coolify_go(chat_id)
    elif data == "install_aapanel_info":    cb_aapanel_info(chat_id)
    elif data == "install_aapanel_go":      cb_aapanel_go(chat_id)
    elif data == "install_aaclaw_info":     cb_aaclaw_info(chat_id)
    elif data == "install_aaclaw_go":       cb_aaclaw_go(chat_id)
    elif data == "install_cloudpanel_info": cb_cloudpanel_info(chat_id)
    elif data.startswith("cp_go_"):         cb_cloudpanel_confirm(chat_id, data[6:])
    elif data.startswith("cp_confirm_"):    cb_cloudpanel_go(chat_id, data[11:])
    elif data == "install_openclaw_info":   cb_openclaw_info(chat_id)
    elif data.startswith("openclaw_go_"):   cb_openclaw_go(chat_id, data[12:])
    elif data == "install_woncode_info":    cb_woncode_info(chat_id)
    elif data == "install_woncode_go":      cb_woncode_go(chat_id)
    elif data == "install_fail2ban_info":   cb_fail2ban_info(chat_id)
    elif data == "install_fail2ban_go":     cb_fail2ban_go(chat_id)
    elif data == "cmd_controle":            cmd_controle_servicos(chat_id)
    elif data.startswith("svc_menu_"):      cb_svc_menu(chat_id, data[9:])
    elif data.startswith("svc_start_"):     cb_svc_executar(chat_id, "start", data[10:])
    elif data.startswith("svc_stop_"):      cb_svc_confirmar(chat_id, "stop", data[9:])
    elif data.startswith("svc_restart_"):   cb_svc_confirmar(chat_id, "restart", data[12:])
    elif data.startswith("svc_do_stop_"):   cb_svc_executar(chat_id, "stop", data[12:])
    elif data.startswith("svc_do_restart_"): cb_svc_executar(chat_id, "restart", data[15:])
    elif data.startswith("svc_install_auto_"): cb_svc_install_auto(chat_id, data[17:])
    elif data == "install_cancel":
        send(chat_id, "❌ Operação cancelada.")
    else:
        send(chat_id, "❓ Ação desconhecida.")


# ─── Monitor automático ────────────────────────────────────────────────────────

_last_alert    = {"cpu": 0, "disk": 0}
ALERT_COOLDOWN = 3600

def get_cpu_usage():
    try:
        out   = run("top -bn1 | grep 'Cpu'")
        match = re.search(r"(\d+[\.,]\d+)\s+id", out)
        if match:
            return round(100 - float(match.group(1).replace(",", ".")), 1)
    except:
        pass
    return None

def get_disk_pct():
    try:
        out   = run("df / | tail -1")
        parts = out.split()
        if len(parts) >= 5:
            return int(parts[4].replace("%", ""))
    except:
        pass
    return None

def monitor_loop():
    logging.info("Monitor de CPU/disco iniciado.")
    while True:
        time.sleep(MONITOR_INTERVAL)
        if not AUTHORIZED_CHAT_ID:
            continue
        try:
            t    = time.time()
            cpu  = get_cpu_usage()
            disk = get_disk_pct()
            if cpu is not None and cpu >= CPU_ALERT_THRESHOLD:
                if t - _last_alert["cpu"] > ALERT_COOLDOWN:
                    _last_alert["cpu"] = t
                    send(AUTHORIZED_CHAT_ID,
                        f"🚨 *ALERTA — CPU alta!*\n📅 {now()}\n\n"
                        f"🔥 Uso atual: *{cpu:.1f}%* (limite: {CPU_ALERT_THRESHOLD}%)\n\nUse /status para mais detalhes."
                    )
                    logging.warning(f"Alerta CPU: {cpu:.1f}%")
            if disk is not None and disk >= DISK_ALERT_THRESHOLD:
                if t - _last_alert["disk"] > ALERT_COOLDOWN:
                    _last_alert["disk"] = t
                    send(AUTHORIZED_CHAT_ID,
                        f"🚨 *ALERTA — Disco cheio!*\n📅 {now()}\n\n"
                        f"💿 Uso atual: *{disk}%* (limite: {DISK_ALERT_THRESHOLD}%)\n\nUse /disco para mais detalhes."
                    )
                    logging.warning(f"Alerta Disco: {disk}%")
        except Exception as e:
            logging.error(f"Erro no monitor: {e}")


# ─── Router ────────────────────────────────────────────────────────────────────

def handle(message):
    global AUTHORIZED_CHAT_ID
    chat_id = message["chat"]["id"]
    user    = message.get("from", {})
    text    = message.get("text", "").strip()

    if AUTHORIZED_CHAT_ID and chat_id != AUTHORIZED_CHAT_ID:
        logging.warning(f"Acesso negado para chat_id {chat_id}")
        return

    if not text:
        return

    # Captura entrada de porta do firewall
    if chat_id in _awaiting_port:
        logging.info(f"Entrada de porta: '{text}' de {chat_id}")
        handle_port_input(chat_id, text)
        return

    cmd  = text.split()[0].lower().lstrip("/").split("@")[0]
    args = text.split()[1:]
    logging.info(f"Comando recebido: {text} de {chat_id}")

    if   cmd in ("start", "menu"):  cmd_start(chat_id, user)
    elif cmd == "monitoramento":    cmd_monitoramento(chat_id)
    elif cmd == "manutencao":       cmd_manutencao(chat_id)
    elif cmd == "status":           cmd_status(chat_id)
    elif cmd == "servicos":         cmd_servicos(chat_id)
    elif cmd == "processos":        cmd_processos(chat_id)
    elif cmd == "rede":             cmd_rede(chat_id)
    elif cmd == "ping":             cmd_ping(chat_id, args[0] if args else "")
    elif cmd == "dns":              cmd_dns(chat_id, args[0] if args else "")
    elif cmd == "disco":            cmd_disco(chat_id)
    elif cmd == "logs":             cmd_logs(chat_id)
    elif cmd == "erros":            cmd_erros(chat_id)
    elif cmd == "docker":          cmd_docker(chat_id)
    elif cmd == "seguranca":        cmd_seguranca(chat_id)
    elif cmd == "fail2ban":         cmd_fail2ban(chat_id)
    elif cmd == "banned":           cmd_banned(chat_id)
    elif cmd == "unban":            cmd_unban(chat_id, args[0] if args else "")
    elif cmd == "firewall":         cmd_firewall(chat_id)
    elif cmd == "controle":         cmd_controle_servicos(chat_id)
    elif cmd == "instalar":         cmd_instalar(chat_id)
    elif cmd == "atualizacoes":     cmd_atualizacoes(chat_id)
    elif cmd == "atualizar":        cmd_atualizar(chat_id)
    elif cmd == "reboot":           cmd_reboot(chat_id)
    elif cmd == "relatorio":       cmd_relatorio(chat_id)
    elif cmd == "confirmarreboot":  cmd_confirmar_reboot(chat_id)
    elif cmd == "cancelar":
        _awaiting_port.pop(chat_id, None)
        send(chat_id, "❌ Operação cancelada.")
    else:
        send(chat_id, "❓ Comando desconhecido. Use /menu para ver os comandos disponíveis.")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    logging.info("Bot iniciado.")
    set_commands()
    threading.Thread(target=monitor_loop, daemon=True).start()

    offset = None
    while True:
        updates = get_updates(offset)
        if not updates.get("ok"):
            time.sleep(5)
            continue
        for update in updates.get("result", []):
            offset = update["update_id"] + 1
            if "message" in update:
                try:
                    handle(update["message"])
                except Exception as e:
                    logging.error(f"Erro ao processar mensagem: {e}")
            elif "callback_query" in update:
                try:
                    handle_callback(update["callback_query"])
                except Exception as e:
                    logging.error(f"Erro ao processar callback: {e}")

if __name__ == "__main__":
    main()
