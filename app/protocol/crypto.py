"""Esqueleto para suporte à criptografia do PUSH SDK (troca de chave pública
+ factor). Fora de escopo na v1 — não implementado.

A v1 apenas detecta e sinaliza na tela quando um handshake chega com
Encrypt != 0, para não confundir "criptografado, não decodifiquei" com
"dispositivo não respondeu".
"""

from typing import Any


def is_encrypted(encrypt_value: Any) -> bool:
    return str(encrypt_value) not in ("0", "", "None")
