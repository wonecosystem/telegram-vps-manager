# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**woncloud-bot** is a Telegram bot for monitoring and managing a Linux server running email/hosting infrastructure (HestiaCP). Written in Python 3 with only `requests` as an external dependency.

## Running the Bot

```bash
# Install (once, requires sudo)
sudo bash install.sh

# Via systemd (production)
sudo systemctl start woncloud-bot
sudo systemctl restart woncloud-bot
sudo systemctl status woncloud-bot

# Manually (development/debugging) — from install directory
cd /opt/woncloud-bot && ./venv/bin/python3 bot.py

# View live logs
tail -f /opt/woncloud-bot/bot.log
sudo journalctl -u woncloud-bot -f
```

## Running Other Scripts

```bash
# Trigger daily report manually
/opt/woncloud-bot/venv/bin/python3 /opt/woncloud-bot/report.py

# Test post-boot notification manually
/opt/woncloud-bot/venv/bin/python3 /opt/woncloud-bot/boot_notify.py
```

## Architecture

Four Python scripts, no frameworks:

- **`bot.py`** — Main process. Runs a long-polling loop against the Telegram Bot API, routes commands to handlers, and runs a background thread that checks CPU/disk every `monitor_interval` seconds and fires alerts when thresholds are exceeded.
- **`report.py`** — Cron job (daily 08:00). Collects server metrics and sends a formatted Telegram report.
- **`boot_notify.py`** — systemd oneshot service. Runs after reboot, waits 15s for stabilization, then sends service status to admin.
- **`install.sh`** — Installs to `/opt/woncloud-bot/`, creates a venv, writes `config.json`, sets up two systemd services and a cron job.

### Key Design Patterns

**Authorization**: The first user to send `/start` registers their `chat_id` in `config.json`. All subsequent commands are rejected if they come from a different chat. This is the sole access control mechanism.

**System commands**: All monitoring data (CPU, RAM, disk, services, Fail2Ban) comes from shell commands executed via `subprocess.run()` with a 15s timeout. There's no abstraction layer — handlers call subprocess directly.

**Reboot workflow**: `/reboot` sets a `reboot_pending` flag with a timestamp. `/confirmarreboot` checks that flag and that fewer than 60 seconds have elapsed before executing `shutdown -r now`.

**Alert cooldown**: `ALERT_COOLDOWN = 3600` seconds. After an alert fires, `last_alert_time` is updated so repeated alerts don't spam the admin during sustained high usage.

## Configuration (`config.json`)

```json
{
  "token": "<telegram-bot-token>",
  "cpu_alert_threshold": 80,
  "disk_alert_threshold": 80,
  "monitor_interval": 300,
  "chat_id": "<registered-chat-id>"
}
```

`chat_id` is written automatically on first `/start`. File is created with mode `600` by the installer.

## Deployment Details

**Services:**
- `woncloud-bot.service` — always-on, auto-restarts on failure (RestartSec=10), runs as root
- `woncloud-boot-notify.service` — oneshot, triggered after boot

**Cron entry added by installer:**
```
0 8 * * * /opt/woncloud-bot/venv/bin/python3 /opt/woncloud-bot/report.py >> /opt/woncloud-bot/report.log 2>&1
```

The bot runs as root because it needs to execute `systemctl`, `fail2ban-client`, and `shutdown`.
