"""CLI de ingestão de uma nota: busca, parseia e grava.

Uso:
    python -m extract.nfce.run "<conteúdo ou URL do QR Code>"
"""
import sys

from extract.db import get_connection
from extract.nfce.client import buscar_html
from extract.nfce.load import salvar_nota
from extract.nfce.parser import parse_nota


def main() -> None:
    if len(sys.argv) != 2:
        print("uso: python -m extract.nfce.run \"<conteúdo ou URL do QR Code>\"")
        raise SystemExit(1)

    html = buscar_html(sys.argv[1])
    nota = parse_nota(html)

    with get_connection() as conn:
        salvar_nota(conn, nota)

    print(f"nota {nota.chave_acesso}: {len(nota.itens)} itens gravados (ON CONFLICT DO NOTHING)")


if __name__ == "__main__":
    main()
