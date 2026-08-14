from __future__ import annotations

import asyncio
import socket
import sys
import time
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # Permite rodar como `python app/main.py` diretamente, sem -m.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from app.config import load_config, save_config
from app.devices import devices
from app.hub import hub
from app.protocol.commands import command_queue
from app.protocol.crypto import is_encrypted
from app.protocol.devicecmd import parse_devicecmd
from app.protocol.handshake import build_handshake_response
from app.protocol.records import parse_records

config = load_config()

app = FastAPI(title="ZKTeco PUSH Tester")


def local_ips() -> list[str]:
    """IPs desta máquina na rede local, para exibir na tela qual endereço
    configurar no ServerIP do equipamento."""
    ips: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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


@app.get("/api/server-info")
async def server_info() -> dict[str, object]:
    """IP(s), porta e modo de protocolo (att/acc) configurados."""
    return {
        "ips": local_ips(),
        "port": config["port"],
        "auto_ok_mode": config.get("auto_ok_mode", False),
        "mode": config.get("mode", "att"),
    }


class ModeRequest(BaseModel):
    mode: str


@app.post("/api/mode")
async def set_mode(payload: ModeRequest) -> dict[str, str]:
    """Troca ATT/ACC pela tela, sem precisar editar config.json e reiniciar.
    Afeta o handshake do próximo GET /iclock/cdata pra qualquer SN."""
    if payload.mode not in ("att", "acc"):
        raise HTTPException(status_code=422, detail="mode deve ser 'att' ou 'acc'")
    config["mode"] = payload.mode
    save_config(config)
    await hub.emit({"type": "mode_changed", "mode": payload.mode})
    return {"mode": payload.mode}


@app.get("/api/devices")
async def list_devices() -> list[dict[str, object]]:
    """SN + último IP visto de cada equipamento que já falou com o servidor,
    para a tela permitir escolher o alvo do comando pelo IP em vez de exigir
    que o operador saiba o SN de cor."""
    return devices.list()


async def tcp_probe(ip: str, port: int, timeout: float = 0.8) -> bool:
    """Tentativa de conexão TCP crua — sinal de que existe algo vivo naquele
    IP, nada mais (equipamentos PUSH são clientes HTTP; não respondem a
    handshake nenhum aqui, só confirma que a porta está aberta)."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        writer.close()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


@app.get("/api/devices/lookup")
async def lookup_device(ip: str) -> dict[str, object]:
    """Botão "Buscar" da tela: cruza o IP digitado com o que já apareceu no
    tráfego real (fonte confiável — é como sabemos o SN) e faz um teste de
    alcance TCP na porta 80 (interface local de configuração, comum nos
    equipamentos ZKTeco) só como sinal auxiliar de que o host está vivo."""
    match = next((d for d in devices.list() if d.get("ip") == ip), None)
    reachable = await tcp_probe(ip, 80)
    return {"ip": ip, "known": match is not None, "device": match, "reachable_port_80": reachable}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await hub.connect(websocket)
    try:
        while True:
            # A tela não envia nada relevante; só mantemos a conexão viva.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)


# Tabelas cujo upload deve ser confirmado com "OK:<n>" (n = registros aceitos),
# por Attendance PUSH Communication Protocol §11.2/11.4/11.6/11.7/11.9-11.14.
# Demais tabelas (ATTPHOTO, BIOPHOTO, ERRORLOG, rtlog/transaction do ACC,
# options) recebem "OK" simples.
COUNTED_TABLES = {"ATTLOG", "OPERLOG", "BIODATA", "IDCARD"}

# ATTPHOTO/identity-card ATTPHOTO trafegam JPEG binário cru após um byte NUL
# (PIN=...\nSN=...\nsize=...\nCMD=uploadphoto\0<binário>) — não pode ser
# decodificado como UTF-8/texto igual às demais tabelas.
PHOTO_TABLES = {"ATTPHOTO"}


@app.get("/iclock/cdata", response_class=PlainTextResponse)
async def cdata_get(request: Request) -> str:
    """Handshake — dispositivo pede a configuração do servidor."""
    sn = request.query_params.get("SN", "unknown")
    ip = client_ip(request)
    devices.touch(sn, ip)
    stamp = str(int(time.time()))
    mode = config.get("mode", "att")
    handshake_cfg = config["handshake"][mode]
    body = build_handshake_response(sn, mode, handshake_cfg, stamp)

    await hub.emit(
        {
            "type": "handshake",
            "method": "GET",
            "path": "/iclock/cdata",
            "sn": sn,
            "ip": ip,
            "mode": mode,
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "response": body,
            "encrypted": mode == "att" and is_encrypted(handshake_cfg.get("Encrypt")),
        }
    )
    return body


@app.post("/iclock/cdata", response_class=PlainTextResponse)
async def cdata_post(request: Request) -> str:
    """Upload de registros (ATTLOG, RTLOG, OPLOG, etc.)."""
    sn = request.query_params.get("SN", "unknown")
    ip = client_ip(request)
    devices.touch(sn, ip)
    table = request.query_params.get("table", "unknown")
    raw_bytes = await request.body()
    table_key = table.upper()

    if table_key in PHOTO_TABLES:
        header, _, binary = raw_bytes.partition(b"\x00")
        header_text = header.decode("utf-8", errors="replace")
        await hub.emit(
            {
                "type": "upload",
                "method": "POST",
                "path": "/iclock/cdata",
                "sn": sn,
                "ip": ip,
                "table": table,
                "query": dict(request.query_params),
                "headers": dict(request.headers),
                "body": header_text,
                "records": [{"table": table, "fields": [f"<binário: {len(binary)} bytes>"]}],
                "response": "OK",
            }
        )
        return "OK"

    raw = raw_bytes.decode("utf-8", errors="replace")
    records = parse_records(table, raw)
    response = f"OK:{len(records)}" if table_key in COUNTED_TABLES else "OK"

    await hub.emit(
        {
            "type": "upload",
            "method": "POST",
            "path": "/iclock/cdata",
            "sn": sn,
            "ip": ip,
            "table": table,
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "body": raw,
            "records": records,
            "response": response,
        }
    )
    return response


@app.post("/iclock/querydata", response_class=PlainTextResponse)
async def querydata(request: Request) -> str:
    """Resposta do dispositivo a DATA QUERY / GET OPTIONS (Security PUSH
    Communication Protocol §9.1.4/§9.5.2) — round-trip de leitura que o ACC
    usa e o ATT não. Sem isso, um painel de acesso recebe 404 ao responder
    a uma consulta."""
    sn = request.query_params.get("SN", "unknown")
    ip = client_ip(request)
    devices.touch(sn, ip)
    raw = (await request.body()).decode("utf-8", errors="replace")
    records = parse_records("querydata", raw)

    await hub.emit(
        {
            "type": "querydata",
            "method": "POST",
            "path": "/iclock/querydata",
            "sn": sn,
            "ip": ip,
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "body": raw,
            "records": records,
            "response": "OK",
        }
    )
    return "OK"


@app.get("/iclock/getrequest", response_class=PlainTextResponse)
async def getrequest(request: Request) -> str:
    """Fila de comandos — responde OK (nada a fazer) ou C:<CmdID>:<comando>."""
    sn = request.query_params.get("SN", "unknown")
    ip = client_ip(request)
    devices.touch(sn, ip)
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
            "ip": ip,
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
    ip = client_ip(request)
    devices.touch(sn, ip)
    raw = (await request.body()).decode("utf-8", errors="replace")
    parsed = parse_devicecmd(raw)  # lista: o dispositivo pode confirmar vários comandos num só POST

    await hub.emit(
        {
            "type": "devicecmd",
            "method": "POST",
            "path": "/iclock/devicecmd",
            "sn": sn,
            "ip": ip,
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "body": raw,
            "parsed": parsed,
        }
    )
    return "OK"


def known_sn(sn: str) -> bool:
    return any(d["sn"] == sn for d in devices.list())


class CommandRequest(BaseModel):
    sn: str
    command: str


@app.post("/api/commands")
async def inject_command(payload: CommandRequest) -> dict[str, object]:
    """Painel de ação da tela: injeta um comando manualmente na fila de um SN."""
    sn = payload.sn.strip()
    if not sn:
        raise HTTPException(status_code=422, detail="SN vazio")
    cmd_id = command_queue.push(sn, payload.command)

    await hub.emit(
        {
            "type": "command_queued",
            "sn": sn,
            "command_id": cmd_id,
            "command": payload.command,
        }
    )
    return {"status": "queued", "command_id": cmd_id, "known_device": known_sn(sn)}


def main() -> None:
    import uvicorn

    print("ZKTeco PUSH Tester")
    print(f"  Tela de monitoramento: http://localhost:{config['port']}")
    print(f"  Configure no equipamento ServerIP/porta apontando para este host na porta {config['port']}")
    uvicorn.run(app, host=config["host"], port=config["port"])


if __name__ == "__main__":
    main()
