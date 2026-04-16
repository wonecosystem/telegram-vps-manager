#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# WonCloud Telegram Bot — Instalador
# ─────────────────────────────────────────────────────────────────────────────
set -e

INSTALL_DIR="/opt/woncloud-bot"
VENV_DIR="$INSTALL_DIR/venv"
PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "${RED}✘ $1${NC}"; exit 1; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   WonCloud Telegram Bot — Instalador"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

[ "$EUID" -ne 0 ] && err "Execute como root: sudo bash install.sh"

# ─── 1. Dependências do sistema ───────────────────────────────────────────────
echo "▶ Verificando dependências..."
apt-get update -qq

for pkg in python3 python3-pip; do
    if ! dpkg -l "$pkg" &>/dev/null; then
        echo "  Instalando $pkg..."
        apt-get install -y -qq "$pkg"
        ok "$pkg instalado"
    else
        ok "$pkg já instalado"
    fi
done

# Detecta versão do Python e instala o pacote venv correto (ex: python3.12-venv)
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
VENV_PKG="python${PY_VER}-venv"
echo "  Instalando $VENV_PKG para Python $PY_VER..."
apt-get install -y -qq "$VENV_PKG" || apt-get install -y -qq python3-venv || true
ok "python venv disponível (Python $PY_VER)"

# ─── 2. Diretório de instalação ───────────────────────────────────────────────
echo ""
echo "▶ Configurando diretório $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for f in bot.py report.py boot_notify.py; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/$f"
        ok "$f copiado"
    else
        err "Arquivo $f não encontrado no diretório atual."
    fi
done

# ─── 3. Ambiente virtual ──────────────────────────────────────────────────────
echo ""
echo "▶ Criando ambiente virtual Python..."
python3 -m venv "$VENV_DIR"
ok "venv criado em $VENV_DIR"

echo "▶ Instalando dependências Python (requests)..."
$PIP install --quiet --upgrade pip
$PIP install --quiet requests
ok "requests instalado"

# ─── 4. Configuração do bot ───────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Configuração"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CONFIG_FILE="$INSTALL_DIR/config.json"

# Preserva config existente se já tiver token
if [ -f "$CONFIG_FILE" ] && grep -q '"token"' "$CONFIG_FILE"; then
    warn "config.json já existe. Mantendo configuração atual."
    EXISTING_TOKEN=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('token',''))" 2>/dev/null)
    if [ -n "$EXISTING_TOKEN" ]; then
        ok "Token existente preservado."
        TOKEN="$EXISTING_TOKEN"
    fi
fi

if [ -z "$TOKEN" ]; then
    echo ""
    read -rp "🤖 Cole o TOKEN do bot Telegram (do @BotFather): " TOKEN
    [ -z "$TOKEN" ] && err "TOKEN não pode ser vazio."

    read -rp "📊 Limite de alerta CPU em % (padrão: 80): " CPU_THRESHOLD
    CPU_THRESHOLD=${CPU_THRESHOLD:-80}

    read -rp "💿 Limite de alerta Disco em % (padrão: 80): " DISK_THRESHOLD
    DISK_THRESHOLD=${DISK_THRESHOLD:-80}

    cat > "$CONFIG_FILE" <<EOF
{
  "token": "$TOKEN",
  "cpu_alert_threshold": $CPU_THRESHOLD,
  "disk_alert_threshold": $DISK_THRESHOLD,
  "monitor_interval": 300
}
EOF
    ok "config.json criado"
fi

chmod 600 "$CONFIG_FILE"

# ─── 5. Serviços systemd ──────────────────────────────────────────────────────
echo ""
echo "▶ Instalando serviços systemd..."

cat > /etc/systemd/system/woncloud-bot.service <<EOF
[Unit]
Description=WonCloud Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$PYTHON $INSTALL_DIR/bot.py
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF
ok "woncloud-bot.service criado"

cat > /etc/systemd/system/woncloud-boot-notify.service <<EOF
[Unit]
Description=WonCloud Boot Notification
After=network-online.target woncloud-bot.service
Wants=network-online.target
Requires=woncloud-bot.service

[Service]
Type=oneshot
ExecStart=$PYTHON $INSTALL_DIR/boot_notify.py
RemainAfterExit=no
User=root

[Install]
WantedBy=multi-user.target
EOF
ok "woncloud-boot-notify.service criado"

# ─── 6. Cron para relatório diário ────────────────────────────────────────────
echo ""
echo "▶ Configurando cron para relatório diário às 08h..."
CRON_LINE="0 8 * * * $PYTHON $INSTALL_DIR/report.py >> $INSTALL_DIR/report.log 2>&1"
( crontab -l 2>/dev/null | grep -v "report.py"; echo "$CRON_LINE" ) | crontab -
ok "Cron configurado"

# ─── 7. Ativar e iniciar ──────────────────────────────────────────────────────
echo ""
echo "▶ Ativando serviços..."
systemctl daemon-reload
systemctl enable woncloud-bot woncloud-boot-notify
systemctl restart woncloud-bot
ok "woncloud-bot iniciado"

# ─── Resumo ───────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}   Instalação concluída com sucesso!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Bot:         $(systemctl is-active woncloud-bot)"
echo "  Config:      $CONFIG_FILE"
echo "  Logs:        $INSTALL_DIR/bot.log"
echo "  Relatório:   $INSTALL_DIR/report.log"
echo ""
echo "  ➡  Abra o Telegram e envie /start para o bot"
echo "     para registrar seu Chat ID."
echo ""
