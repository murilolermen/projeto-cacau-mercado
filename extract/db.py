"""Conexão com o Postgres (Supabase) usada pelos jobs de extração/carga.

Só este pipeline usa a `service_role` (ignora RLS) — nunca o frontend
(ADR-006). Por isso a leitura de `SUPABASE_DB_URL` é obrigatória: se a env
var não existir, é melhor o processo quebrar na hora (KeyError) do que
seguir silenciosamente sem banco configurado.
"""
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection() -> psycopg.Connection:
    return psycopg.connect(os.environ["SUPABASE_DB_URL"])
