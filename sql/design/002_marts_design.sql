-- 002_marts_design.sql
--
-- ⚠️  DESIGN — NÃO EXECUTAR CONTRA O BANCO. Não é uma migration: é a
-- tradução column-a-column das decisões já registradas em decisoes.md
-- (ADRs 005, 007, 008, 009, 010, 011, 016, 017, 018) para DDL concreta.
-- Fecha a pendência "Consolidar SQL" listada no próprio decisoes.md.
--
-- Na Fase 3 (setup do dbt), cada CREATE TABLE abaixo vira um model dbt
-- (staging → intermediate → marts) — dbt materializa a tabela, ninguém
-- roda isto à mão. Este arquivo existe para não perder nenhuma decisão
-- na tradução de prosa para schema.
--
-- origem: reaproveita o tipo `raw.origem_dado` (ADR-017) — a mesma regra
-- de proveniência vale em marts quanto em raw.

-- ── dim_item_consumo ────────────────────────────────────────────────────
-- O genérico ("Leite semidesnatado 1L"). A LISTA aponta aqui, nunca para
-- uma marca — consumo se mede neste nível, não no produto (ADR-011).
CREATE TABLE marts.dim_item_consumo (
    item_consumo_sk   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_generico     text NOT NULL UNIQUE,
    unidade_base      text NOT NULL,          -- g, ml, un — base da taxa de consumo (ADR-009)
    origem            raw.origem_dado NOT NULL DEFAULT 'nfce'
);

-- ── dim_produto ─────────────────────────────────────────────────────────
-- O específico (loja + código interno). Preço se mede aqui, não no
-- genérico — marca é tudo para preço: Tirol ≠ Piá (ADR-011).
CREATE TABLE marts.dim_produto (
    produto_sk        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Chave natural composta, NÃO GTIN (ADR-005). Estável dentro da loja
    -- (permite cache permanente do enriquecimento, ADR-013); sem
    -- correspondência entre lojas — por isso existe dim_item_consumo.
    cnpj_emitente     char(14) NOT NULL,
    codigo_interno    text NOT NULL,

    descricao_nota    text NOT NULL,          -- última descrição vista na nota para este código
    item_consumo_sk   bigint REFERENCES marts.dim_item_consumo (item_consumo_sk),
                                               -- nullable: resolução de identidade (ADR-013) pode não ter rodado ainda

    marca             text,
    variante          text,
    qtd_embalagem     numeric(12, 3) NOT NULL,  -- ex: 500 (g) — mesma normalização usada na taxa de consumo (ADR-009)
    unidade_base      text NOT NULL,            -- g, ml, un

    -- Atributo do PRODUTO, não do evento de compra (ADR-010): perguntar a
    -- cada adição à lista seria fricção, e fricção mata a feature (ADR-008).
    is_recorrente     boolean NOT NULL DEFAULT true,

    origem            raw.origem_dado NOT NULL DEFAULT 'nfce',
    criado_em         timestamptz NOT NULL DEFAULT now(),
    atualizado_em     timestamptz NOT NULL DEFAULT now(),

    UNIQUE (cnpj_emitente, codigo_interno)
);

-- ── fato_item_compra — transacional ────────────────────────────────────
-- Grão: 1 item de 1 nota. Imutável — nunca muda depois de gravado (ADR-007).
CREATE TABLE marts.fato_item_compra (
    chave_acesso              char(44) NOT NULL,
    item_seq                  integer NOT NULL,

    produto_sk                bigint NOT NULL REFERENCES marts.dim_produto (produto_sk),
    data_compra                date NOT NULL,

    quantidade                numeric(12, 3) NOT NULL,

    -- Preço de TABELA (Vl. Unit cheio da nota) — ground truth para série
    -- histórica, comparação de marca/loja e índice de preços. Preço
    -- EFETIVO (o que de fato saiu do bolso) é outra grandeza, capturada em
    -- fato_item_lista via etiqueta da gôndola. Não confundir as duas aqui
    -- (ADR-016).
    valor_unitario_tabela      numeric(12, 4) NOT NULL,
    valor_total_item_tabela    numeric(12, 2) NOT NULL,

    origem                     raw.origem_dado NOT NULL DEFAULT 'nfce',

    PRIMARY KEY (chave_acesso, item_seq)   -- idempotência: reprocessar não duplica
);

-- ── fato_estoque_casa — periodic snapshot ──────────────────────────────
-- Grão fechado em item_consumo (não em produto, apesar da redação literal
-- do ADR-007). Motivo: o ADR-011 é explícito que consumo se mede no
-- genérico, não na marca ("você não consome marca, consome leite"), e a
-- taxa de consumo (ADR-009) já é calculada nesse nível — fatiar estoque
-- por produto exigiria saber de antemão qual marca será comprada a
-- seguir, o que não é conhecido. ADR-007 antecede o ADR-011; a palavra
-- "produto" ali foi informal, não uma decisão fechada sobre este grão.
-- Decidido em 2026-08-14.
CREATE TABLE marts.fato_estoque_casa (
    item_consumo_sk       bigint NOT NULL REFERENCES marts.dim_item_consumo (item_consumo_sk),
    data_snapshot         date NOT NULL,

    -- Derivado, nunca editado à mão: qtd_última_compra − (taxa_consumo ×
    -- dias_decorridos). Recalculado pelo pipeline a cada snapshot.
    estoque_estimado      numeric(12, 3) NOT NULL,
    taxa_consumo_diaria   numeric(12, 4),      -- unidade_base/dia (ADR-009); null sem histórico suficiente

    origem                raw.origem_dado NOT NULL DEFAULT 'nfce',

    PRIMARY KEY (item_consumo_sk, data_snapshot)
);

-- ── fato_sessao_compra ──────────────────────────────────────────────────
-- Uma ida ao mercado. valor_total NÃO é coluna — é sempre
-- `SELECT sum(valor_total_item_tabela) FROM fato_item_compra GROUP BY ...`
-- (ADR-018). Guardar o total aqui reintroduziria o bug do
-- read-modify-write (lost update + erro de ponto flutuante). Definida
-- antes de fato_item_lista porque esta última referencia sessao_sk.
CREATE TABLE marts.fato_sessao_compra (
    sessao_sk       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data_sessao     timestamptz NOT NULL,
    chave_acesso    char(44),      -- preenchido quando a nota chega e concilia
    origem          raw.origem_dado NOT NULL DEFAULT 'manual'
);

-- ── fato_item_lista — accumulating snapshot ────────────────────────────
-- Grão: 1 item adicionado à lista. A linha EVOLUI — cada marco carimba uma
-- coluna de data diferente na MESMA linha (ADR-007):
--   pendente → em_sessao → comprado → conciliado
CREATE TABLE marts.fato_item_lista (
    lista_item_sk      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    item_consumo_sk     bigint NOT NULL REFERENCES marts.dim_item_consumo (item_consumo_sk),
                                          -- a LISTA aponta pro genérico (ADR-011); a marca se decide na gôndola

    -- O dado mais valioso do sistema (ADR-008). Nunca deletar a linha, só
    -- arquivar — é exatamente o soft delete que faltava (erro #11 do log
    -- de erros corrigidos).
    data_adicao         timestamptz NOT NULL,

    status              text NOT NULL DEFAULT 'pendente',
                                          -- pendente | em_sessao | comprado | conciliado
    data_em_sessao      timestamptz,
    data_comprado        timestamptz,
    data_conciliado        timestamptz,

    -- Preenchidos progressivamente conforme a linha evolui:
    sessao_sk               bigint REFERENCES marts.fato_sessao_compra (sessao_sk),
    produto_sk                 bigint REFERENCES marts.dim_produto (produto_sk),
                                          -- qual marca/loja de fato saiu — só se sabe em "comprado"
    chave_acesso                  char(44),   -- liga à nota real ao conciliar
    item_seq                         integer,

    -- Os três preços do mesmo item (ADR-016 + seção 5 do handoff):
    preco_estimado                      numeric(12, 4),  -- modelo, antes de ir ao mercado
    preco_observado                        numeric(12, 4),  -- digitado na gôndola
    preco_tabela                              numeric(12, 4),  -- da nota, depois de conciliar

    origem                                       raw.origem_dado NOT NULL DEFAULT 'manual'
);

-- ── fato_indicador ──────────────────────────────────────────────────────
-- Séries macro (IBGE/SIDRA, BCB Focus). Alimenta o deflacionamento por
-- subitem e o índice de Laspeyres doméstico — não previsão (ADR-019).
CREATE TABLE marts.fato_indicador (
    indicador_sk    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fonte           text NOT NULL,             -- 'ibge_sidra' | 'bcb_focus'
    subitem         text NOT NULL,             -- ex: 'leite longa vida'; cheio só para índices agregados
    competencia     char(6) NOT NULL,          -- AAAAMM
    valor           numeric(12, 4) NOT NULL,
    origem          raw.origem_dado NOT NULL DEFAULT 'nfce'
);
