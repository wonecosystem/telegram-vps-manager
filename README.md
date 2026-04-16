# 🤖 Telegram VPS Manager

> **Gerencie seu servidor Linux direto pelo Telegram — sem acessar terminal.**

[![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)](https://python.org)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-26A5E4?logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![License](https://img.shields.io/badge/Licença-MIT-green)](LICENSE)
[![Won Ecosystem](https://img.shields.io/badge/Won-Ecosystem-orange)](https://wonecosystem.com.br)

---

## 📋 Sobre o Projeto

**Telegram VPS Manager** é um bot para Telegram que permite monitorar e gerenciar servidores Linux (VPS/Dedicados) diretamente pelo celular ou desktop, sem necessidade de cliente SSH ou terminal.

Desenvolvido com foco em **simplicidade, segurança e praticidade**, ideal para administradores que precisam de acesso rápido ao servidor em qualquer lugar.

---

## ✨ Funcionalidades

### 🖥️ Monitoramento
| Comando | Descrição |
|---|---|
| `/status` | CPU, RAM, disco e uptime em tempo real |
| `/servicos` | Status dos serviços instalados (Nginx, Docker, etc.) |
| `/processos` | Top processos por CPU e RAM |
| `/rede` | IP público, interfaces de rede e portas em escuta |
| `/disco` | Uso detalhado de disco em todas as partições |
| `/logs` | Logs do sistema: Auth, Syslog e Dmesg |

### 🔒 Segurança
| Comando | Descrição |
|---|---|
| `/fail2ban` | Relatório completo por jail |
| `/banned` | Lista de IPs banidos agora |
| `/unban <ip>` | Desbanir um IP de todos os jails |
| `/firewall` | Gerenciar UFW: ativar, abrir e fechar portas |
| `/ping <host>` | Ping + rota com até 5 saltos via tracepath |
| `/dns <dominio>` | Consulta registros DNS: A, MX, NS, TXT, CNAME |

### 📦 Instalações via Telegram
- ⭐ **Won Code** — Agente de programação autônomo com IA
- 🛠️ **aaPanel** — Painel de hospedagem completo
- 🛠️ **aaPanel + OpenClaw** — aaPanel com plugin OpenClaw
- ☁️ **CloudPanel** — Painel moderno (MySQL 8.4/8.0, MariaDB 11.4/10.11)
- 🚀 **Coolify** — Plataforma self-hosted (alternativa ao Heroku)
- 🐳 **EasyPanel** — Painel Docker com Let's Encrypt
- 🔒 **Fail2Ban** — Proteção automática contra ataques
- 🦅 **OpenClaw** — Agente de IA no terminal

### ⚙️ Manutenção
| Comando | Descrição |
|---|---|
| `/atualizar` | `apt update && apt upgrade -y` com notificação ao concluir |
| `/reboot` | Reiniciar o servidor com confirmação de segurança |

### 🔔 Alertas Automáticos
- Alerta de **CPU alta** quando ultrapassar o limite configurado
- Alerta de **disco cheio** com percentual atual
- **Notificação pós-reboot** com status dos serviços
- **Relatório diário** automático às 08h

---

## 🔐 Segurança

- Acesso restrito a **um único chat_id** registrado no primeiro `/start`
- Firewall com **porta 22 protegida permanentemente** (não pode ser bloqueada)
- Reboot exige **confirmação explícita** com expiração de 60 segundos
- Instalações exigem **confirmação com botões** antes de executar
- CloudPanel verifica **sha256** do instalador antes de executar
- `config.json` com permissão `600` (somente o dono lê)

---

## 🚀 Instalação

### Pré-requisitos
- Servidor Linux (Ubuntu 22.04+ recomendado)
- Acesso root (via SSH ou painel da VPS)
- Token de bot Telegram (veja como obter abaixo)

---

### Passo 1 — Criar o bot no Telegram

1. Abra o Telegram e pesquise por **@BotFather**
2. Envie o comando `/newbot`
3. Escolha um nome para o bot (ex: `Meu Servidor Bot`)
4. Escolha um username terminando em `bot` (ex: `meuservidor_bot`)
5. O BotFather vai te enviar um **TOKEN** — copie e guarde, você vai precisar

> Exemplo de token: `7861641200:AAERSgi8WxuiRv1fDwtWsi-Ejvzw47FtsFA`

---

### Passo 2 — Acessar o servidor via SSH

Se você usa **Windows**, abra o **PowerShell** ou **CMD** e conecte:

```bash
ssh root@IP_DO_SEU_SERVIDOR
```

> Substitua `IP_DO_SEU_SERVIDOR` pelo IP da sua VPS (ex: `ssh root@123.456.789.0`)

---

### Passo 3 — Instalar o bot (tudo em um comando)

Cole os comandos abaixo no terminal do servidor:

```bash
apt update && apt install -y git
git clone https://github.com/wonecosystem/telegram-vps-manager.git
cd telegram-vps-manager
sudo bash install.sh
```

O instalador vai perguntar:

```
🤖 Cole o TOKEN do bot Telegram (do @BotFather): [cole aqui o token]
📊 Limite de alerta CPU em % (padrão: 80):        [Enter para 80%]
💿 Limite de alerta Disco em % (padrão: 80):      [Enter para 80%]
```

Ao final você verá:
```
✔ Instalação concluída com sucesso!
```

---

### Passo 4 — Ativar o bot no Telegram

1. Abra o Telegram
2. Pesquise pelo username do bot que você criou (ex: `@meuservidor_bot`)
3. Envie `/start`
4. O bot vai registrar seu usuário e exibir o menu completo

> ⚠️ O primeiro usuário que enviar `/start` fica como administrador. Outros usuários serão bloqueados automaticamente.

---

### Atualizar para uma versão mais recente

Quando houver novos recursos disponíveis, basta rodar na VPS:

```bash
cd ~/telegram-vps-manager && git pull && sudo bash install.sh
```

> O instalador detecta que o bot já está configurado e **preserva seu token e configurações** automaticamente — sem precisar digitar nada novamente.

---

### Instalar como serviço (recomendado)

```bash
sudo bash install.sh
```

O instalador configura automaticamente:
- Ambiente virtual Python
- Serviço systemd `woncloud-bot` (reinicia automaticamente se cair)
- Serviço systemd `woncloud-boot-notify` (notifica no Telegram após reboot)
- Cron job para relatório diário às 08h

---

## 📁 Estrutura

```
telegram-vps-manager/
├── bot.py              # Bot principal (polling + handlers + monitor)
├── report.py           # Relatório diário (executado pelo cron)
├── boot_notify.py      # Notificação pós-reboot (systemd oneshot)
├── install.sh          # Instalador automático
└── config.json         # Configuração (ignorado pelo git)
```

---

## ⚙️ Configuração avançada

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `token` | — | Token do bot Telegram |
| `chat_id` | auto | Registrado no primeiro `/start` |
| `cpu_alert_threshold` | `80` | % de CPU para disparar alerta |
| `disk_alert_threshold` | `80` | % de disco para disparar alerta |
| `monitor_interval` | `300` | Intervalo de monitoramento em segundos |

---

## 👨‍💻 Desenvolvedor

<table>
  <tr>
    <td align="center">
      <b>Glauco Martins</b><br>
      Fundador & Dev — Won Ecosystem<br><br>
      <a href="https://www.instagram.com/glaucormartins">📸 @glaucormartins</a><br>
      <a href="https://wa.me/5527998670627">💬 WhatsApp (27) 99867-0627</a>
    </td>
  </tr>
</table>

---

## 🏢 Won Ecosystem Serviços LTDA

**CNPJ:** 65.444.304/0001-93

| Produto | Link |
|---|---|
| 🌐 Won Ecosystem | [wonecosystem.com.br](https://wonecosystem.com.br) |
| 💻 Won Code — Agente de IA | [woncode.com.br](https://woncode.com.br) |
| 🔌 Won Code App — APIs (CEP, CNPJ, WhatsApp, Router AI...) | [app.woncode.com.br](https://app.woncode.com.br) |
| 💳 Won Pay — PIX, Checkout e Área de Membros | [wonpay.com.br](https://wonpay.com.br) |

### 📱 Redes Sociais

[![YouTube](https://img.shields.io/badge/YouTube-Won%20Ecosystem-FF0000?logo=youtube&logoColor=white)](https://www.youtube.com/@wonecosystem)
[![Instagram](https://img.shields.io/badge/Instagram-wonacademy__-E4405F?logo=instagram&logoColor=white)](https://www.instagram.com/wonacademy_)
[![Instagram](https://img.shields.io/badge/Instagram-glaucormartins-E4405F?logo=instagram&logoColor=white)](https://www.instagram.com/glaucormartins)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-(27)%2099867--0627-25D366?logo=whatsapp&logoColor=white)](https://wa.me/5527998670627)

---

## 📄 Licença

Este projeto é distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<p align="center">
  Feito com ❤️ por <a href="https://wonecosystem.com.br">Won Ecosystem</a>
</p>
