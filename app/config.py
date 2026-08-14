import json
import sys
from pathlib import Path
from typing import Any

# "att" = terminais de ponto (Attendance PUSH Communication Protocol);
# "acc" = controladoras de acesso (Security PUSH Communication Protocol).
# Os dois protocolos usam um handshake (GET /iclock/cdata) com formato
# diferente — ver app/protocol/handshake.py.
DEFAULTS: dict[str, Any] = {
    "host": "0.0.0.0",
    "port": 8081,
    "auto_ok_mode": False,
    "mode": "att",
    "handshake": {
        "att": {
            "ErrorDelay": 30,
            "Delay": 10,
            "TransTimes": "00:00;14:05",
            "TransInterval": 1,
            "TransFlag": "TransData AttLog\tOpLog\tAttPhoto\tEnrollUser\tChgUser\tEnrollFP\tChgFP\tUserPic\tWORKCODE\tBioPhoto",
            "TimeZone": 0,
            "Realtime": 1,
            "Encrypt": 0,
            "ServerVer": "2.4.2",
            "PushProtVer": "2.4.2",
            "PushOptionsFlag": 1,
            "PushOptions": "FingerFunOn,FaceFunOn",
        },
        "acc": {
            "ServerVersion": "3.1.2",
            "ServerName": "ZKTeco PUSH Tester",
            "PushProtVer": "3.1.2",
            "ErrorDelay": 30,
            "RequestDelay": 10,
            "TransTimes": "00:00;14:05",
            "TransInterval": 1,
            "TransTables": "user,transaction,ReaderProperty,DoorProperty,DoorParameters",
            "Realtime": 1,
            "TimeoutSec": 60,
        },
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
        config["mode"] = user_config.get("mode", config["mode"])
        handshake_user = user_config.get("handshake", {})
        config["handshake"]["att"].update(handshake_user.get("att", {}))
        config["handshake"]["acc"].update(handshake_user.get("acc", {}))

    return config


def save_config(config: dict[str, Any], path: Path | None = None) -> None:
    """Grava o config em uso de volta no config.json — usado pela troca de
    `mode` (ATT/ACC) pela tela, pra persistir entre reinícios."""
    config_path = path or (base_dir() / "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
