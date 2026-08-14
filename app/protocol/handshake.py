import secrets
from typing import Any

# Attendance PUSH Communication Protocol 20250429 (§5) — apenas estes campos,
# nesta ordem, formam o handshake do lado ATT.
ATT_FIELDS = (
    "ErrorDelay",
    "Delay",
    "TransTimes",
    "TransInterval",
    "TransFlag",
    "TimeZone",
    "Realtime",
    "Encrypt",
    "ServerVer",
    "PushProtVer",
    "PushOptionsFlag",
    "PushOptions",
)

# Security PUSH Communication Protocol 20250429 (§4.1) — campos do handshake
# do lado ACC, formato completamente diferente do ATT.
ACC_FIELDS = (
    "ServerVersion",
    "ServerName",
    "PushProtVer",
    "ErrorDelay",
    "RequestDelay",
    "TransTimes",
    "TransInterval",
    "TransTables",
    "Realtime",
)


def build_att_handshake_response(sn: str, cfg: dict[str, Any], stamp: str) -> str:
    """GET /iclock/cdata para terminais ATT (Attendance).

    A spec usa ${LF} (\\n) como terminador e stamps por tabela
    (ATTLOGStamp/OPERLOGStamp/ATTPHOTOStamp), não um Stamp genérico.
    """
    lines = [
        f"GET OPTION FROM: {sn}",
        f"ATTLOGStamp={stamp}",
        f"OPERLOGStamp={stamp}",
        f"ATTPHOTOStamp={stamp}",
    ]
    for key in ATT_FIELDS:
        lines.append(f"{key}={cfg[key]}")
    return "\n".join(lines) + "\n"


def build_acc_handshake_response(sn: str, cfg: dict[str, Any], stamp: str) -> str:
    """GET /iclock/cdata para controladoras ACC (Access/Security).

    Formato de registro (§4.1): registry=ok + RegistryCode/SessionID, usados
    pelo dispositivo nas próximas requisições. RegistryCode/SessionID são
    gerados por conexão; a spec não define o algoritmo, só que o servidor
    os emite.
    """
    lines = [
        "registry=ok",
        f"RegistryCode={secrets.token_hex(4)}",
    ]
    for key in ACC_FIELDS:
        lines.append(f"{key}={cfg[key]}")
    lines.append(f"SessionID={secrets.token_hex(8)}")
    lines.append(f"TimeoutSec={cfg['TimeoutSec']}")
    return "\n".join(lines) + "\n"


def build_handshake_response(sn: str, mode: str, cfg: dict[str, Any], stamp: str) -> str:
    if mode == "acc":
        return build_acc_handshake_response(sn, cfg, stamp)
    return build_att_handshake_response(sn, cfg, stamp)
