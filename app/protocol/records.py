from typing import Any


def parse_records(table: str, body: str) -> list[dict[str, Any]]:
    """Parse cru do corpo do POST /iclock/cdata.

    Cada linha é um registro; campos separados por TAB. A v1 não interpreta
    o significado semântico dos campos por tabela (ATTLOG, RTLOG, OPLOG...),
    apenas exibe cru já quebrado por campo.
    """
    records: list[dict[str, Any]] = []
    for raw_line in body.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip("\r")
        if not line:
            continue
        records.append({"table": table, "fields": line.split("\t")})
    return records
