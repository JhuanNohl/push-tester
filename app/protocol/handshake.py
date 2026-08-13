from typing import Any

HANDSHAKE_FIELDS = (
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


def build_handshake_response(sn: str, handshake_config: dict[str, Any], stamp: str) -> str:
    """Monta o corpo de resposta do GET /iclock/cdata (handshake).

    Uma diretiva por linha, terminada em \\r\\n, como o dispositivo espera.
    """
    lines = [f"GET OPTION FROM: {sn}", f"Stamp={stamp}", f"OpStamp={stamp}"]
    for key in HANDSHAKE_FIELDS:
        lines.append(f"{key}={handshake_config[key]}")
    return "\r\n".join(lines) + "\r\n"
