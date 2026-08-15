-- Staging do item da nota: 1:1 com raw.nfce_item (ADR-004). Mesmo filtro
-- de origem do stg_nfce_nota (ADR-017) — as duas staging tables precisam
-- concordar sobre o que é "dado real" antes de qualquer join adiante.

select
    chave_acesso,
    item_seq,
    codigo_interno,
    descricao,
    quantidade,
    unidade,
    valor_unitario_tabela,
    valor_total_item_tabela,
    origem,
    capturado_em
from {{ source('raw', 'nfce_item') }}
where origem <> 'teste'
