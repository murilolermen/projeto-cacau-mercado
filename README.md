# Cacau

**Plataforma de dados sobre consumo doméstico, construída a partir de notas fiscais eletrônicas (NFC-e).**

Responde a perguntas que um extrato bancário não responde:

- *Meu arroz subiu mais que a inflação oficial?*
- *Quanto vou gastar nesta compra, antes de passar no caixa?*
- *Em quantos dias o café vai acabar?*
- *Quanto me custa a fidelidade a uma marca?*

> **Sobre o nome:** Cacau é a cachorra da casa. Também é o nome do aplicativo de lista de compras que originou este projeto — em uso diário por duas pessoas há meses. A plataforma de dados nasceu da necessidade real, não do contrário.

---

## Status

**Fase de design.** O modelo de dados e as decisões arquiteturais estão documentados; a implementação começa a seguir.

O documento central deste repositório, hoje, é o [**Registro de Decisões Arquiteturais**](./DECISOES.md) — 19 decisões, cada uma com contexto, alternativas rejeitadas e consequências.

> Este projeto é construído **design-first**: as decisões vêm antes do código. Os erros de modelagem também estão documentados — a seção *"Erros cometidos e corrigidos"* do ADR é intencional.

### Roteiro

- [x] Validação da fonte de dados (spike da NFC-e)
- [x] Modelo dimensional (3 fatos Kimball)
- [x] Registro de decisões arquiteturais
- [ ] Parser da NFC-e com higienização de PII
- [ ] Pipeline dbt (`raw` → `staging` → `marts`)
- [ ] Enriquecimento de produto (entity resolution)
- [ ] Ingestão de séries macro (IBGE/SIDRA, BCB)
- [ ] Camada de análise (Streamlit)

---

## Contexto

Não é um projeto sobre um dataset baixado. É a plataforma de dados de uma **aplicação em uso real**.

Essa origem é o que dá substância ao trabalho. Vários dos problemas modelados aqui **não apareceriam em dado sintético**:

- O usuário adiciona o produto **antes** de ele acabar → o evento de interesse é **censurado** ([ADR-010](./DECISOES.md#adr-010))
- Ele troca de marca conforme o preço → o erro do modelo precisa ser **decomposto em preço × mix × volume** ([ADR-012](./DECISOES.md#adr-012))
- A nota fiscal **não traz código de barras**, só o código interno da loja → comparar preço entre mercados exige **resolução de identidade** ([ADR-005](./DECISOES.md#adr-005))
- Existe vocabulário doméstico que nenhum modelo genérico resolve — *"alburgue"* é hambúrguer, e só um dicionário curado sabe disso ([ADR-013](./DECISOES.md#adr-013))

---

## Arquitetura

```
      Nota fiscal (QR Code)          Séries macro (IBGE, BCB, ANP)
                │                                │
                ▼                                ▼
        ┌───────────────────────────────────────────┐
        │  raw      payload bruto, imutável         │
        │  staging  tipado, limpo, deduplicado      │
        │  marts    modelo dimensional (star)       │
        └───────────────────────────────────────────┘
                │                                │
                ▼                                ▼
          Streamlit                         PWA (lista)
          (análise)                    (serving pré-computado)
```

| Camada | Tecnologia |
|---|---|
| Ingestão | Python |
| Orquestração | GitHub Actions (cron) |
| Transformação | dbt-core |
| Armazenamento | PostgreSQL (Supabase) |
| Análise | Streamlit |

Custo de infraestrutura: **R$ 0**.

---

## Decisões que definem o projeto

| ADR | Decisão |
|---|---|
| [001](./DECISOES.md#adr-001) | Validar a fonte antes de construir — e por que a API de preços do estado foi descartada |
| [007](./DECISOES.md#adr-007) | Três tipos de fato Kimball, todos naturais — incluindo um *accumulating snapshot* |
| [008](./DECISOES.md#adr-008) | O consumo é **derivado do comportamento**, nunca contado à mão |
| [010](./DECISOES.md#adr-010) | O dado é **censurado** — e por que Kaplan-Meier foi deliberadamente descartado |
| [015](./DECISOES.md#adr-015) | Nenhum modelo preditivo de série temporal, e o porquê |
| [017](./DECISOES.md#adr-017) | Toda linha carrega sua **origem** — linhagem no nível da linha |
| [019](./DECISOES.md#adr-019) | **Deflacionar, não prever** — índice de Laspeyres doméstico contra o IPCA oficial |

---

## Privacidade

Notas fiscais contêm **CPF e nome do consumidor**. O parser descarta esses campos **antes da gravação** — eles nunca entram no banco ([ADR-006](./DECISOES.md#adr-006)).

Nenhum dado real é versionado. O ambiente de demonstração usa **dados sintéticos**.

---

## Licença

MIT
