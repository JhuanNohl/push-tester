import json
import sys
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "host": "0.0.0.0",
    "port": 8080,
    "auto_ok_mode": False,
    "handshake": {
        "ErrorDelay": 30,
        "Delay": 10,
        "TransTimes": "00:00;14:05",
        "TransInterval": 1,
        "TransFlag": "1111111111",
        "TimeZone": 0,
        "Realtime": 1,
        "Encrypt": 0,
        "ServerVer": "2.4.2",
        "PushProtVer": "2.4.2",
        "PushOptionsFlag": 1,
        "PushOptions": "FingerFunOn,FaceFunOn",
    },
}


def base_dir() -> Path:
    """Pasta onde procurar config.json: ao lado do .exe quando empacotado,
    ou raiz do projeto em modo dev."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or (base_dir() / "config.json")
    config = json.loads(json.dumps(DEFAULTS))  # deep copy dos defaults

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config["host"] = user_config.get("host", config["host"])
        config["port"] = user_config.get("port", config["port"])
        config["auto_ok_mode"] = user_config.get("auto_ok_mode", config["auto_ok_mode"])
        config["handshake"].update(user_config.get("handshake", {}))

    return config
