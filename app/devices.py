import time
from typing import Any


class DeviceRegistry:
    """Mapeamento SN -> último IP/horário visto, construído a partir do
    tráfego real recebido. O protocolo sempre identifica o equipamento pelo
    SN (é o que ele manda em cada request e a chave da fila de comandos),
    mas a tela pode usar isso para deixar o operador escolher o equipamento
    pelo IP, que é o que ele configurou/conhece de cabeça."""

    def __init__(self) -> None:
        self._devices: dict[str, dict[str, Any]] = {}

    def touch(self, sn: str | None, ip: str | None) -> None:
        if not sn or sn == "unknown":
            return
        self._devices[sn] = {"sn": sn, "ip": ip, "last_seen": time.time()}

    def list(self) -> list[dict[str, Any]]:
        return sorted(self._devices.values(), key=lambda d: d["last_seen"], reverse=True)


devices = DeviceRegistry()
