-- Staging da nota fiscal: 1:1 com raw.nfce_nota (ADR-004) — renomeia e
-- filtra lixo de desenvolvimento, nenhuma lógica de negócio aqui.
--
-- WHERE origem <> 'teste' é o "filtro trivial" do ADR-017: dado de teste
-- nunca é deletado na raw, só marcado — é aqui que ele para de existir
-- pro resto do pipeline.

select
    chave_acesso,
    uf_emitente,
    competencia,
    cnpj_emitente,
    numero_nota,
    serie_nota,
    valor_total_nota,
    desconto_total,
    origem,
    capturado_em
from {{ source('raw', 'nfce_nota') }}
where origem <> 'teste'
