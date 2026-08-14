"""Grava uma NotaFiscal já parseada em raw.nfce_nota / raw.nfce_item.

Idempotente (ADR-017/seção de idempotência do handoff): o cron de
ingestão pode repetir a mesma nota, então todo INSERT usa
ON CONFLICT DO NOTHING — reprocessar não duplica.
"""
from psycopg import Connection

from extract.nfce.parser import NotaFiscal


def salvar_nota(conn: Connection, nota: NotaFiscal) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.nfce_nota (
                chave_acesso, uf_emitente, competencia, cnpj_emitente,
                numero_nota, serie_nota, valor_total_nota, desconto_total,
                html_bruto
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chave_acesso) DO NOTHING
            """,
            (
                nota.chave_acesso,
                nota.uf_emitente,
                nota.competencia,
                nota.cnpj_emitente,
                nota.numero_nota,
                nota.serie_nota,
                nota.valor_total_nota,
                nota.desconto_total,
                nota.html_bruto,
            ),
        )

        for item in nota.itens:
            cur.execute(
                """
                INSERT INTO raw.nfce_item (
                    chave_acesso, item_seq, codigo_interno, descricao,
                    quantidade, unidade, valor_unitario_tabela,
                    valor_total_item_tabela
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chave_acesso, item_seq) DO NOTHING
                """,
                (
                    nota.chave_acesso,
                    item.item_seq,
                    item.codigo_interno,
                    item.descricao,
                    item.quantidade,
                    item.unidade,
                    item.valor_unitario_tabela,
                    item.valor_total_item_tabela,
                ),
            )

    conn.commit()
