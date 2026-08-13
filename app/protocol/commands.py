import itertools
from typing import Optional


class CommandQueue:
    """Fila de comandos pendentes por número de série (SN).

    O dispositivo consulta via GET /iclock/getrequest; cada comando pendente
    é formatado como ``C:<CmdID>:<comando>``. Fila vazia responde ``OK``.
    """

    def __init__(self) -> None:
        self._queues: dict[str, list[tuple[int, str]]] = {}
        self._id_counter = itertools.count(1)

    def push(self, sn: str, command_text: str) -> int:
        cmd_id = next(self._id_counter)
        self._queues.setdefault(sn, []).append((cmd_id, command_text))
        return cmd_id

    def pop(self, sn: str) -> Optional[str]:
        queue = self._queues.get(sn)
        if not queue:
            return None
        cmd_id, command_text = queue.pop(0)
        return f"C:{cmd_id}:{command_text}"

    def pending(self, sn: str) -> list[str]:
        return [f"C:{cmd_id}:{text}" for cmd_id, text in self._queues.get(sn, [])]


command_queue = CommandQueue()
