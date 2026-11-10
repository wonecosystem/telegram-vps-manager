import json
import os
import pathlib
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]

# config temporario: o bot valida o token no import
_cfg_dir = pathlib.Path(tempfile.mkdtemp())
_cfg = _cfg_dir / "config.json"
_cfg.write_text(json.dumps({
    "token": "000000:TESTE",
    "chat_id": 424242,
    "cpu_alert_threshold": 80,
    "disk_alert_threshold": 80,
    "monitor_interval": 300,
}), encoding="utf-8")
os.environ["WONCLOUD_BOT_CONFIG"] = str(_cfg)

sys.path.insert(0, str(RAIZ))
