from urllib.parse import parse_qsl


def parse_devicecmd(body: str) -> list[dict[str, str]]:
    """Parse do retorno de comando enviado pelo dispositivo em
    POST /iclock/devicecmd.

    Corpo form-encoded, uma confirmação por linha
    (``ID=<CmdID>&Return=<código>&CMD=<...>``); o dispositivo pode confirmar
    vários comandos pendentes num único POST, uma linha por comando.
    """
    results: list[dict[str, str]] = []
    for raw_line in body.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip("\r")
        if not line:
            continue
        results.append(dict(parse_qsl(line, keep_blank_values=True)))
    return results
