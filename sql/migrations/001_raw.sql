-- 001_raw.sql
--
-- Camada raw: o que o parser Python extrai da NFC-e, sem transformação de
-- negócio (ADR-004 — raw é append-only, imutável, "nunca transformar
-- aqui"). PII (CPF/nome do consumidor) nunca chega nesta tabela: o parser
-- descarta esses campos antes do INSERT (ADR-006), não depois.
--
-- Idempotência: chave_acesso é a PK natural da nota (44 dígitos, emitida
-- pela SEFA). O cron de ingestão pode atrasar e repetir — todo INSERT
-- contra estas tabelas deve usar ON CONFLICT DO NOTHING.

CREATE SCHEMA IF NOT EXISTS raw;

-- Origem da linha (ADR-017). Enum, não texto livre — senão o próprio campo
-- criado pra resolver o problema de proveniência termina com 'teste',
-- 'TESTE', 'test', 'tst', e o filtro `WHERE origem <> 'teste'` para de ser
-- confiável.
CREATE TYPE raw.origem_dado AS ENUM ('nfce', 'manual', 'legado', 'teste', 'seed');

-- Uma nota fiscal. Grão: 1 linha por nota.
CREATE TABLE raw.nfce_nota (
    chave_acesso        char(44)        PRIMARY KEY,

    -- Decompostos da própria chave de acesso, sem precisar de request
    -- extra (ADR-001): UF(2) AAMM(4) CNPJ(14) modelo(2) série(3) número(9)
    -- tpEmis(1) cNF(8) DV(1).
    uf_emitente          char(2)         NOT NULL,
    competencia            char(4)         NOT NULL,  -- AAMM de emissão
    cnpj_emitente            char(14)        NOT NULL,
    numero_nota                text            NOT NULL,
    serie_nota                    text            NOT NULL,

    -- Agregados do rodapé. O desconto por item NÃO existe no HTML público
    -- (ADR-016) — só o total. Não se rateia aqui: seria inventar dado que
    -- nunca esteve na gôndola.
    valor_total_nota                numeric(12, 2),
    desconto_total                     numeric(12, 2),

    -- Payload íntegro, guardado de propósito: se o parser de itens tiver
    -- bug (e vai ter), reprocessa-se staging/marts a partir daqui sem
    -- perder nada (ADR-004). Nunca conter o bloco "Consumidor" (CPF/nome)
    -- — descartado pelo parser antes deste INSERT (ADR-006).
    html_bruto                            text            NOT NULL,

    origem                                  raw.origem_dado NOT NULL DEFAULT 'nfce',
    capturado_em                              timestamptz     NOT NULL DEFAULT now()
);

-- Um item de uma nota. Grão: 1 linha por item por nota.
CREATE TABLE raw.nfce_item (
    chave_acesso          char(44)        NOT NULL REFERENCES raw.nfce_nota (chave_acesso),
    item_seq                 integer         NOT NULL,   -- posição do item no cupom (1, 2, 3...)

    -- Chave natural do produto é (CNPJ do emitente, código interno da
    -- loja), NÃO o GTIN — a consulta pública só traz cProd, nunca cEAN
    -- (ADR-005).
    codigo_interno              text            NOT NULL,
    descricao                      text            NOT NULL,

    quantidade                        numeric(12, 3)  NOT NULL,
    unidade                              text            NOT NULL,

    -- "Vl. Unit" da nota vem CHEIO — é preço de TABELA, não o preço
    -- efetivamente pago (ADR-016). Preço efetivo é outra grandeza, de
    -- outra fonte (etiqueta digitada na gôndola) — não vive nesta tabela.
    valor_unitario_tabela                  numeric(12, 4)  NOT NULL,
    valor_total_item_tabela                   numeric(12, 2)  NOT NULL,

    origem                                       raw.origem_dado NOT NULL DEFAULT 'nfce',
    capturado_em                                   timestamptz     NOT NULL DEFAULT now(),

    PRIMARY KEY (chave_acesso, item_seq)   -- idempotência: reprocessar não duplica
);
