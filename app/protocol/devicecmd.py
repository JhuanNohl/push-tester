from urllib.parse import parse_qsl


def parse_devicecmd(body: str) -> dict[str, str]:
    """Parse do retorno de comando enviado pelo dispositivo em
    POST /iclock/devicecmd (corpo form-encoded: ID=<CmdID>&Return=<código>&CMD=<...>).
    """
    return dict(parse_qsl(body, keep_blank_values=True))
