from __future__ import annotations

import sys
import time
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # Permite rodar como `python app/main.py` diretamente, sem -m.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from app.config import load_config
from app.hub import hub
from app.protocol.commands import command_queue
from app.protocol.crypto import is_encrypted
from app.protocol.devicecmd import parse_devicecmd
from app.protocol.handshake import build_handshake_response
from app.protocol.records import parse_records

config = load_config()

app = FastAPI(title="ZKTeco PUSH Tester")


def web_dir() -> Path:
    """Pasta com o index.html: recurso embutido (_MEIPASS) quando empacotado
    com PyInstaller, ou app/web em modo dev."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "app" / "web"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "web"


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html_path = web_dir() / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await hub.connect(websocket)
    try:
        while True:
            # A tela não envia nada relevante; só mantemos a conexão viva.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)


@app.get("/iclock/cdata", response_class=PlainTextResponse)
async def cdata_get(request: Request) -> str:
    """Handshake — dispositivo pede a configuração do servidor."""
    sn = request.query_params.get("SN", "unknown")
    stamp = str(int(time.time()))
    handshake_cfg = config["handshake"]
    body = build_handshake_response(sn, handshake_cfg, stamp)

    await hub.emit(
        {
            "type": "handshake",
            "method": "GET",
            "path": "/iclock/cdata",
            "sn": sn,
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "response": body,
            "encrypted": is_encrypted(handshake_cfg.get("Encrypt")),
        }
    )
    return body


@app.post("/iclock/cdata", response_class=PlainTextResponse)
async def cdata_post(request: Request) -> str:
    """Upload de registros (ATTLOG, RTLOG, OPLOG, etc.)."""
    sn = request.query_params.get("SN", "unknown")
    table = request.query_params.get("table", "unknown")
    raw = (await request.body()).decode("utf-8", errors="replace")
    records = parse_records(table, raw)

    await hub.emit(
        {
            "type": "upload",
            "method": "POST",
            "path": "/iclock/cdata",
            "sn": sn,
            "table": table,
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "body": raw,
            "records": records,
        }
    )
    return "OK"


@app.get("/iclock/getrequest", response_class=PlainTextResponse)
async def getrequest(request: Request) -> str:
    """Fila de comandos — responde OK (nada a fazer) ou C:<CmdID>:<comando>."""
    sn = request.query_params.get("SN", "unknown")
    if config.get("auto_ok_mode"):
        response = "OK"
    else:
        response = command_queue.pop(sn) or "OK"

    await hub.emit(
        {
            "type": "getrequest",
            "method": "GET",
            "path": "/iclock/getrequest",
            "sn": sn,
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "response": response,
        }
    )
    return response


@app.post("/iclock/devicecmd", response_class=PlainTextResponse)
async def devicecmd(request: Request) -> str:
    """Retorno da execução de um comando pelo dispositivo."""
    sn = request.query_params.get("SN", "unknown")
    raw = (await request.body()).decode("utf-8", errors="replace")
    parsed = parse_devicecmd(raw)

    await hub.emit(
        {
            "type": "devicecmd",
            "method": "POST",
            "path": "/iclock/devicecmd",
            "sn": sn,
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "body": raw,
            "parsed": parsed,
        }
    )
    return "OK"


class CommandRequest(BaseModel):
    sn: str
    command: str


@app.post("/api/commands")
async def inject_command(payload: CommandRequest) -> dict[str, object]:
    """Painel de ação da tela: injeta um comando manualmente na fila de um SN."""
    cmd_id = command_queue.push(payload.sn, payload.command)

    await hub.emit(
        {
            "type": "command_queued",
            "sn": payload.sn,
            "command_id": cmd_id,
            "command": payload.command,
        }
    )
    return {"status": "queued", "command_id": cmd_id}


def main() -> None:
    import uvicorn

    print("ZKTeco PUSH Tester")
    print(f"  Tela de monitoramento: http://localhost:{config['port']}")
    print(f"  Configure no equipamento ServerIP/porta apontando para este host na porta {config['port']}")
    uvicorn.run(app, host=config["host"], port=config["port"])


if __name__ == "__main__":
    main()
