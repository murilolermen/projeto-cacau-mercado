# Registro de Decisões Arquiteturais (ADR)

> Projeto: **pantry-data-platform**
> Plataforma de dados sobre compras de supermercado, alimentada por notas fiscais eletrônicas (NFC-e).
> Última atualização: julho/2026

---

## Por que este documento existe

Código mostra **o que** foi feito. Este documento mostra **por que** — e, mais importante, **o que foi descartado e por quê**.

Cada decisão segue o mesmo formato:

- **Contexto** — o problema real que apareceu
- **Decisão** — o que foi escolhido
- **Alternativas rejeitadas** — e o motivo da rejeição
- **Consequências** — o que essa escolha custa

Várias decisões aqui são **correções de erros cometidos no desenho inicial**. Elas estão documentadas de propósito: a evolução do modelo é o registro mais honesto do processo de engenharia.

---

## Índice

| # | Decisão | Área |
|---|---|---|
| [ADR-001](#adr-001) | Validar a fonte de dados antes de construir qualquer coisa | Processo |
| [ADR-002](#adr-002) | Duas aplicações, dois repositórios, um banco | Arquitetura |
| [ADR-003](#adr-003) | Streamlit para análise, não para captura | Arquitetura |
| [ADR-004](#adr-004) | Camadas raw → staging → marts | Engenharia de dados |
| [ADR-005](#adr-005) | Chave natural do produto é composta, não GTIN | Modelagem |
| [ADR-006](#adr-006) | Descartar PII antes de gravar | Segurança / LGPD |
| [ADR-007](#adr-007) | Três tipos de fato, todos naturais | Modelagem |
| [ADR-008](#adr-008) | Consumo é derivado da lista, nunca contado | Modelagem |
| [ADR-009](#adr-009) | Consumo é taxa, não intervalo | Modelagem |
| [ADR-010](#adr-010) | Dado censurado: capturar o rótulo, não modelar a latência | Estatística |
| [ADR-011](#adr-011) | Camada de item genérico como ponte entre marcas e lojas | Modelagem |
| [ADR-012](#adr-012) | Erro decomposto em preço × mix × volume | Análise |
| [ADR-013](#adr-013) | LLM para entity resolution, com cache e revisão humana | Engenharia de dados |
| [ADR-014](#adr-014) | Serving layer pré-computada | Arquitetura |
| [ADR-015](#adr-015) | Sem modelo preditivo de série temporal | Ciência de dados |
| [ADR-016](#adr-016) | Preço de tabela e preço efetivo são grandezas distintas | Modelagem |
| [ADR-017](#adr-017) | Toda linha carrega sua origem | Governança |
| [ADR-018](#adr-018) | Nunca armazenar o que pode ser derivado | Engenharia de dados |
| [ADR-019](#adr-019) | Deflacionar, não prever: IPCA por subitem e índice de Laspeyres | Ciência de dados |

---

<a name="adr-001"></a>
## ADR-001 — Validar a fonte de dados antes de construir qualquer coisa

**Contexto**

Todo o projeto depende de uma premissa: conseguir ler a NFC-e de forma programática. Se o portal da SEFA exigisse captcha ou autenticação, a arquitetura inteira desabaria.

**Decisão**

Executar um *spike* de meio dia **antes** de escrever qualquer linha de schema ou pipeline: pegar uma nota real, resolver o QR Code, ver o que volta.

**Resultado**

A URL do QR (`fazenda.pr.gov.br/nfce/qrcode?p=...`) responde a um `GET` simples e devolve o DANFE em HTML puro. Sem captcha, sem login, sem token.

Bônus: a chave de acesso de 44 dígitos é **parseável offline**, sem nenhuma requisição:

| Trecho | Campo |
|---|---|
| `41` | UF (Paraná) |
| `2606` | Ano/mês de emissão |
| `76189406001955` | **CNPJ do emitente** |
| `65` | Modelo (65 = NFC-e) |
| `122` | Série |
| `000347161` | Número da nota |
| `…8` | Dígito verificador (módulo 11) |

O DV permite **validar a integridade do QR antes de bater no servidor** — vira um teste de qualidade na camada raw.

**Alternativas rejeitadas**

- *Assumir que funciona e começar pelo schema* — teria custado semanas de modelagem sobre fundação não verificada.
- *Usar a API do app "Menor Preço" do Nota Paraná* — **descartado por violar o Termo de Uso.** A cláusula 3.3(g) veda expressamente "utilizar os serviços da Plataforma em outro aplicativo ou site", e a 5.2(ix) veda "criar um banco de dados por meio de downloads sistemáticos". O endpoint é tecnicamente acessível (sem autenticação), mas **ausência de cadeado não é autorização**.

**Consequências**

A restrição legal empurrou o projeto para uma fonte **melhor**: a própria nota fiscal do usuário. É dado próprio, sem termo de terceiro limitando o uso, e com granularidade muito superior — item a item, com quantidade e preço unitário.

> **Lição:** ler o Termo de Uso antes de escrever código economiza mais tempo que qualquer otimização.

---

<a name="adr-002"></a>
## ADR-002 — Duas aplicações, dois repositórios, um banco

**Contexto**

O projeto tem duas naturezas incompatíveis:

1. **Captura** — usada no corredor do supermercado, no celular, com câmera, em rede instável.
2. **Análise** — usada em casa, no desktop, com gráficos densos e bibliotecas científicas.

**Decisão**

| Componente | Tecnologia | Hospedagem | Repositório |
|---|---|---|---|
| Captura (PWA) | React + Vite | Vercel | Privado |
| Plataforma de dados | Python + dbt | GitHub Actions | **Público (portfólio)** |
| Análise | Streamlit | Streamlit Cloud | Público (mesmo repo) |
| Banco | PostgreSQL | Supabase | — |

O **banco é o único contrato** entre as duas aplicações. Nenhum código é compartilhado.

**Alternativas rejeitadas**

- *Uma app só, em Streamlit* — falha no requisito de mobilidade (ver ADR-003).
- *Uma app só, em React* — jogaria fora o ecossistema científico do Python, que é o objetivo do portfólio.
- *Empacotar o Streamlit num WebView e virar APK* — a captura depende de câmera nativa; a UX seria sofrível.

**Consequências**

Duas hospedagens para manter. Aceitável: ambas são gratuitas, e a separação é **ditada por requisito, não por preferência** — o que é justamente a justificativa defensável.

> Custo total de infraestrutura: **R$ 0**. Portfólio precisa ficar de pé por anos sem manutenção paga.

---

<a name="adr-003"></a>
## ADR-003 — Streamlit para análise, não para captura

**Contexto**

Streamlit resolveria a captura tecnicamente (`st.camera_input` funciona). A tentação de usar uma ferramenta só era grande.

**Decisão**

Streamlit **não** faz captura. É exclusivamente a camada de análise, read-only.

**Motivos**

1. **Hibernação** — o free tier dorme sem tráfego. Abrir o app no mercado e esperar 60s de cold start é o fim do uso real.
2. **Rerun completo** — cada interação re-executa o script inteiro. Insuportável no 4G do supermercado.
3. **Sem offline** — não tem service worker. Corredor de mercado é buraco de sinal.
4. **Não instala** — sem ícone, sem cara de app.

> **Lição:** ferramenta de análise forçada a virar produto vira as duas coisas pela metade.

---

<a name="adr-004"></a>
## ADR-004 — Camadas raw → staging → marts

**Contexto**

Onde colocar a lógica de parsing, normalização e enriquecimento.

**Decisão**

Três camadas, com responsabilidades estritas:

| Camada | Conteúdo | Regra |
|---|---|---|
| `raw` | Payload original da nota | **Append-only. Imutável. Nunca transformar aqui.** |
| `staging` | Tipado, limpo, deduplicado | 1:1 com a fonte |
| `marts` | Modelo dimensional | O que o Streamlit e a PWA consomem |

E a decisão que amarra tudo: **a PWA escreve apenas em `raw`.** Ela captura o QR e insere a URL crua — um `INSERT` burro.

Todo o parsing, normalização, resolução de produto e cálculo é **Python, no pipeline**.

**Por que isso importa**

Se o parser tiver um bug (e vai ter), você **reprocessa `marts` a partir de `raw`** sem perder um único dado. Se a PWA já tivesse parseado e descartado o original, o dado estaria perdido para sempre.

Efeito colateral desejável: **100% da engenharia interessante mora no repositório público.**

---

<a name="adr-005"></a>
## ADR-005 — Chave natural do produto é composta, não GTIN

**Contexto**

O desenho inicial assumiu que a nota traria o GTIN (código de barras) de cada item. **Assunção errada** — pelo menos pela via acessível.

A consulta pública (HTML) traz o **código interno da loja**:

```
LEITE TIROL SEMIDESNATADO 1L UHT (Código: 1133271)
                                          ^^^^^^^
                                  código interno do Condor
```

**Descoberta posterior:** o cupom de papel traz o **GTIN** (`07896256603446`) para o mesmo item. Ambos existem no XML — a consulta pública apenas escolhe renderizar o `cProd` (código interno) em vez do `cEAN`.

Como o XML completo não é acessível sem certificado digital, **na prática só há o código interno.**

**Decisão**

A chave natural de um produto é `(CNPJ_do_emitente, código_interno)`.

**Consequências — e este é o problema central do projeto**

- ✅ **Dentro** de uma loja, o código é perfeitamente estável. O `1133271` do Condor é o mesmo leite hoje e daqui a dois anos. Isso permite **cache permanente** do enriquecimento (ver ADR-013).
- ❌ **Entre** lojas, não há chave comum. O mesmo leite tem outro código no Muffato.
- ❌ Hortifruti nem GTIN tem: `BATATA BRANCA LAVADA KG (Código: 17060)` — é PLU interno.

Comparar preço entre mercados exige uma **camada de resolução de identidade** (ADR-011 e ADR-013).

> Este obstáculo é, na verdade, **o coração do projeto de engenharia de dados**. Sem ele, seria um CRUD.

---

<a name="adr-006"></a>
## ADR-006 — Descartar PII antes de gravar

**Contexto**

A consulta da NFC-e retorna, quando o consumidor informou CPF na compra, **o CPF e o nome completo em texto claro**:

```
#### Consumidor
- CPF: XXX.XXX.XXX-XX
- Nome: NOME COMPLETO DO CONSUMIDOR
```

Notas guardadas podem conter dados de **terceiros**, não apenas do dono do app.

**Decisão**

O parser **descarta CPF e nome do consumidor antes de gravar em `raw`.** Não é anonimização posterior — o dado nunca entra.

**Por que é inegociável**

O repositório é **público**. Uma vez commitado, o dado está no histórico do git para sempre — deletar depois não resolve: é preciso reescrever o histórico *e* rotacionar tudo.

Além disso, esses campos são **inúteis** para todos os objetivos do projeto. Guardar dado pessoal sem finalidade é exatamente o que a LGPD veda (princípio da necessidade, art. 6º, III).

**Regras associadas**

- `.gitignore` com `.env` **antes** de criar o `.env` — não depois
- Credenciais em GitHub Secrets / Streamlit Secrets, nunca no código
- Push protection ativado no repositório
- Streamlit lê `marts` com um role **read-only** dedicado
- Seeds e demos usam **dados sintéticos**, nunca notas reais
- A `service_role` key do Supabase **ignora RLS** — jamais no frontend, jamais em repositório público
- Dados de saúde (medicação, suplementos) permanecem **fora do escopo** desta plataforma: são dado pessoal sensível (LGPD art. 11), com nível de proteção distinto

---

<a name="adr-007"></a>
## ADR-007 — Três tipos de fato, todos naturais

> **Revisado (2026-08-14).** O grão de `fato_estoque_casa` foi refinado de "produto" para **`item_consumo`** ao traduzir esta decisão em DDL (`sql/design/002_marts_design.sql`). Motivo: o ADR-011, escrito depois deste, é explícito que consumo se mede no genérico, não na marca — e a taxa de consumo (ADR-009) já é calculada nesse nível. Fatiar estoque por produto exigiria saber de antemão qual marca será comprada a seguir, o que não é conhecido. A palavra "produto" na tabela abaixo era redação informal, não uma decisão fechada sobre este grão especificamente.

**Contexto**

O processo real envolve três coisas que mudam em ritmos diferentes: a compra (evento), o estoque em casa (estado) e o item na lista (processo).

**Decisão**

Três tabelas de fato, uma de cada tipo canônico de Kimball:

| Tabela | Tipo | Grão | Por que este tipo |
|---|---|---|---|
| `fato_item_compra` | **Transacional** | 1 item de 1 nota | Evento imutável. Nunca muda depois de gravado. |
| `fato_estoque_casa` | **Periodic snapshot** | 1 item_consumo × 1 dia | Estado medido periodicamente. Existe linha mesmo sem movimento. |
| `fato_item_lista` | **Accumulating snapshot** | 1 item adicionado à lista | **A linha evolui.** Cada marco carimba uma data. |

**Sobre o accumulating snapshot**

É o tipo mais raro e mais mal-compreendido. Aqui ele apareceu **naturalmente**, sem ser forçado:

```
pendente  →  em_sessao  →  comprado  →  conciliado
   │            │             │             │
adicionou    viu na        passou no    nota fiscal
na lista     gôndola        caixa        chegou
```

Cada transição preenche colunas diferentes da **mesma linha**.

**Consequência**

Ter os três tipos, e saber justificar por que cada um é aquele tipo, cobre a pergunta clássica de entrevista de modelagem dimensional — com um caso real.

---

<a name="adr-008"></a>
## ADR-008 — Consumo é derivado da lista, nunca contado

**Contexto**

O desenho inicial previa uma tabela `contagem_despensa`: o usuário contaria manualmente o que tem em casa.

**Problema**

**Ninguém faz isso.** Feature morta na primeira semana.

E a prova é empírica: o app real rodou dois meses com uma tabela `produtos` para cadastro estruturado. Ela terminou com **4 registros**. Todo o resto foi digitado como texto livre. **O mundo real venceu o cadastro.**

**Decisão**

Matar a contagem manual. **O evento de adicionar o item à lista JÁ É o sinal de consumo.**

Você adiciona ovo porque acabou. Isso é uma observação, não uma opinião:

```
adiciona ovo:  03/jan  →  15/jan  →  28/jan
                     12 dias    13 dias

→ um estoque de ovo dura ~12 dias nesta casa
```

**Consequências**

- Zero fricção. A feature funciona a partir de um comportamento que o usuário já tem.
- Requer marcar quais produtos são recorrentes (`is_recorrente`). Carne de churrasco não é consumo — é ocasião, e polui a série.
- **Torna `lista_compras.data_adicao` o dado mais valioso do sistema.** Um bug que o deletava (soft delete ausente) estava destruindo silenciosamente a matéria-prima do projeto.

> **Lição:** feature que exige disciplina do usuário é feature que morre. Derive o sinal do comportamento que já existe.

---

<a name="adr-009"></a>
## ADR-009 — Consumo é taxa, não intervalo

**Contexto**

A primeira implementação do ADR-008 media o **intervalo médio entre adições**. Bug grave.

**O problema**

```
Compra 1 cartela de ovo   →  dura 12 dias  →  intervalo = 12
Compra 2 cartelas de ovo  →  dura 24 dias  →  intervalo = 24
```

O consumo **não mudou**. Só a quantidade comprada mudou. Mas o modelo aprenderia dois números contraditórios para o mesmo hábito.

Idem para peso: 250 g de café dura metade do tempo de 500 g.

**Decisão**

Medir **taxa de consumo em unidade base**:

```
consumo_diário = (quantidade × qtd_embalagem) ÷ dias_de_duração

500 g ÷ 30 dias = 16,6 g/dia
250 g ÷ 15 dias = 16,6 g/dia   ← mesma taxa. correto.
```

**Consequências**

- Ciclos com quantidades diferentes agora **concordam** entre si. Cada compra vira uma observação válida do mesmo parâmetro, em vez de uma contradição.
- Obriga a normalizar embalagem (`qtd_embalagem`, `unidade_base`) — que é o **mesmo par de campos** já necessário para comparar preço (R$/kg). Uma normalização, dois problemas resolvidos.
- Desbloqueia uma feature real: *"comprando 500 g, dura até 12/08; comprando 250 g, até 28/07"* — escolher o tamanho da embalagem com a data de ruptura na tela.

---

<a name="adr-010"></a>
## ADR-010 — Dado censurado: capturar o rótulo, não modelar a latência

**Contexto**

O evento que interessa é **"o produto acabou em casa"**. Mas ele nunca é observado. O que se observa é **"o usuário adicionou à lista"** — e o usuário antecipa: adiciona o ovo dois dias antes de acabar.

Formalmente: o tempo até o evento é **censurado**.

**Decisão**

Não modelar a latência. **Capturar o rótulo na interface**, com um toque:

> `[ acabou ]`  `[ tá acabando ]`

Default em "acabou". Opcional. Isso converte a variável latente em **dado observado**.

Complementarmente, a **recorrência é atributo do produto**, não do evento (`dim_produto.is_recorrente`) — marcada uma vez, no cadastro. Perguntar a cada adição seria fricção, e fricção mata a feature (ADR-008).

**Alternativas rejeitadas**

- *Análise de sobrevivência (Kaplan-Meier, modelos de tempo até evento)* — é a ferramenta **formalmente correta** para dado censurado. Rejeitada porque, com ~6 ciclos por produto por ano, o custo de complexidade não se paga e o resultado seria ruído com aparência de rigor.
- *Ignorar a antecipação* — introduziria viés sistemático nas datas absolutas de ruptura.

> **Saber que o dado é censurado e escolher deliberadamente não aplicar Kaplan-Meier é uma posição mais defensável do que aplicar Kaplan-Meier em 6 pontos.** Julgamento é a competência escassa, não repertório.

---

<a name="adr-011"></a>
## ADR-011 — Camada de item genérico como ponte entre marcas e lojas

**Contexto**

Dois problemas que pareciam separados, e são o mesmo:

1. **Marca** — o usuário adiciona "leite" na lista, mas compra Tirol hoje e Piá semana que vem, conforme o preço. Para o banco, são produtos diferentes → cada um com 1 ciclo → **o modelo de consumo nunca aprende nada**.
2. **Loja** (ADR-005) — o mesmo leite tem código interno diferente em cada mercado.

**Decisão**

Uma camada de identidade acima do produto:

```
dim_item_consumo  ("Leite semidesnatado 1L")     ← a LISTA aponta aqui
    ├── (Condor,  cód 1133271)  "LEITE TIROL SEMIDESNATADO 1L UHT"
    ├── (Condor,  cód 998877)   "LEITE PIÁ SEMIDESNATADO 1L"
    └── (Muffato, cód 88291)    "LEITE UHT TIROL SEMIDESN 1LT"   ← a NOTA aponta aqui
```

**Cada métrica no seu nível:**

| Métrica | Nível | Por quê |
|---|---|---|
| **Consumo** | `item_consumo` | Você não consome marca. Você consome leite. |
| **Preço** | produto (loja + código) | Marca é tudo. Tirol ≠ Piá. |
| **Lista** | `item_consumo` | Você quer leite. A marca se decide na gôndola. |

**Consequências**

Resolve os dois problemas com uma estrutura só. É a peça central da arquitetura — e **emergiu de um requisito de negócio**, não de um diagrama feito antes de olhar o dado.

---

<a name="adr-012"></a>
## ADR-012 — Erro decomposto em preço × mix × volume

**Contexto**

O modelo estimou R$ 6,50 (Tirol). O usuário pagou R$ 4,90 (Piá). **O modelo errou R$ 1,60?**

Não. O modelo não errou nada — **o usuário mudou de escolha.**

Sem separar isso, o MAPE fica terrível e a culpa cai no modelo, quando a causa era substituição de marca. **Um modelo mal avaliado é pior que um modelo ruim**, porque leva a decisões erradas sobre ele.

**Decisão**

Decompor a diferença entre previsto e realizado em três componentes:

| Componente | O que é | Causa |
|---|---|---|
| **Preço** | Tirol subiu de 6,50 para 6,90 | Mercado |
| **Mix** | Levou Piá em vez de Tirol | Usuário |
| **Volume** | Levou 2 em vez de 1 | Usuário |

Só o componente **preço** é erro do modelo. Os outros dois são comportamento.

**Análises que isso desbloqueia**

- *"Quanto me custa a fidelidade à marca?"* — R$ X a mais em 12 meses insistindo em Tirol.
- *"Elasticidade de substituição"* — a partir de qual diferença percentual o usuário troca de marca.
- Tela pós-compra: *"Previsto R$ 187 → Real R$ 176. Economia de R$ 11: você trocou 3 marcas."*

> Decomposição preço/mix/volume é instrumento clássico de análise de margem. Aplicado aqui, resolve um problema de avaliação de modelo.

---

<a name="adr-013"></a>
## ADR-013 — LLM para entity resolution, com cache e revisão humana

**Contexto**

Extrair marca, variante e gramatura de descrições sujas:

```
BISC.ISABELA RECH.MOUSSE CHOCLEITE 130G
BISC.PIRAQUE MALTADO BLACK BAUN.85G
LEITE TIROL SEMIDESNATADO 1L UHT
MOLHO TOMATE PRATELLE TRAD.300G SACHE
```

A marca está em posição diferente em cada uma. `BISC.` é categoria abreviada, `RECH.` é "recheado", `TRAD.` é "tradicional". **Não há padrão.**

E há o caso que nenhum modelo genérico resolve:

```
"Alburgue"  →  hambúrguer   (apelido doméstico, piada interna do casal)
"Quiboa"    →  água sanitária
"Coube flor" → couve-flor   (erro de digitação recorrente)
```

**Decisão**

Resolução em cascata, com três estágios:

```
1. dim_apelido     — dicionário curado do vocabulário da casa (dbt seed, CSV versionado)
2. LLM (Groq)      — extração de atributos estruturados, em batch
3. Fila humana     — confiança baixa vai para revisão manual no Streamlit
```

**Salvaguardas**

1. **Cache pelo código interno.** O código é estável (ADR-005). Resolve-se **uma vez por produto novo**, nunca mais. O problema deixa de ser "parsear 10.000 linhas" e vira **"resolver ~500 produtos ao longo da vida do app"**.
2. **Teste de qualidade.** Um `dbt test` garante que nenhum produto fique órfão de `item_consumo_sk`. Se ficar, o build falha.

**Alternativas rejeitadas**

- *Regex* — acerta ~60% e a lista de exceções não converge.
- *Fuzzy matching (Levenshtein) direto entre lojas* — `"LEITE TIROL SEMIDESN 1L"` e `"LEITE TIROL INTEGRAL 1L"` têm distância pequena e são **produtos diferentes**. Casaria errado e **envenenaria a série de preço silenciosamente** — o pior tipo de bug.

**Por que o LLM funciona aqui**

Ele não faz o casamento. Ele extrai **atributos estruturados** (marca, variante, tamanho). O casamento entre lojas acontece nos atributos, não na string.

**Nota de modelo**

É um job de **batch** — ninguém espera na tela. Logo, latência é irrelevante e a escolha correta é o **modelo mais preciso**, não o mais rápido. Isso **inverte** a lógica usual de uso do Groq.

---

<a name="adr-014"></a>
## ADR-014 — Serving layer pré-computada

**Contexto**

A PWA precisa mostrar o preço estimado de cada item da lista, em tempo real, no corredor do mercado.

**Decisão**

A PWA **não calcula nada**. Ela faz `SELECT` em `marts.produto_preco_esperado` — uma linha por produto, atualizada pelo pipeline no cron.

**Consequências**

- O app é instantâneo mesmo com a análise sendo pesada.
- Se a previsão levar 30 segundos para rodar, **não importa**: roda no cron.
- Toda a inteligência permanece no repositório público (ADR-004).

> A pergunta de entrevista *"e se o modelo demorasse 30s?"* tem resposta pronta.

---

<a name="adr-015"></a>
## ADR-015 — Sem modelo preditivo de série temporal

**Contexto**

A tentação de colocar Prophet, LSTM ou XGBoost para "prever preços futuros".

**Decisão**

**Não.** Nenhum modelo paramétrico de série temporal sobre os dados pessoais.

**Motivo**

Um produto comprado uma vez por mês gera ~12 observações por ano, ruidosas. Nenhum modelo faz milagre com isso. Um XGBoost sobre 12 pontos não demonstra domínio de XGBoost — demonstra **não saber quando não usar**.

**O que é feito no lugar**

| Método | Aplicação |
|---|---|
| Mediana móvel + banda p25–p75 | Preço esperado |
| Último preço ajustado pelo IPCA do subitem | Produtos com pouco histórico (ver ADR-019) |
| Z-score | *"R$ 8,90 está 1,4 desvios abaixo do que você costuma pagar"* |
| Decomposição sazonal | Apenas nas séries macro (IBGE, ANP), que têm N suficiente |

O campo `confianca` (`sem_historico` / `fraca` / `boa` / `alta`) é exibido na interface.

> **Modelo que não sabe quando não sabe é modelo perigoso.**

---

<a name="adr-016"></a>
## ADR-016 — Preço de tabela e preço efetivo são grandezas distintas

> **Revisado.** A versão inicial supunha que o desconto era apenas agregado. A comparação entre o cupom de papel e a consulta pública provou o contrário.

**Contexto**

A consulta HTML mostra o desconto **apenas no total** (R$ 2,30). O cupom de papel mostra **por item**:

```
002  BISC.ISABELA RECH.MOUSSE CHOCLEITE 130G      2,99
     1UN X 2,99  T12,00%
desconto item 002                                -0,50     ← ausente no HTML
```

Ou seja:

- **`Vl. Unit` vem CHEIO** — é o preço de tabela, não o preço pago.
- O desconto é **linha separada**, por item, aplicada no caixa.
- Os descontos individuais (itens 002, 010, 011, 012) somam exatamente os R$ 2,30 do rodapé.
- **A consulta pública é LOSSY**: descarta a atribuição do desconto ao item.

Um pipeline construído apenas sobre o HTML registraria R$ 2,99 para um biscoito comprado por R$ 2,49 — **erro sistemático para cima, concentrado exatamente nos itens em promoção.**

**Decisão**

Não ratear o desconto. Reconhecer que são **três grandezas diferentes**, cada uma com sua fonte:

| Grandeza | Fonte | Serve para |
|---|---|---|
| **Preço de tabela** | `Vl. Unit` da nota | Série histórica, comparação de marca e loja, índice de preços |
| **Desconto total** | Rodapé da nota | Métrica de economia: *"poupei R$ 47 este mês"* |
| **Preço efetivo** | **Etiqueta digitada na gôndola** | *"Quanto vou passar no caixa"* |

**Consequência — inversão de papéis**

O preço observado na gôndola **deixa de ser conveniência e vira fonte primária** do preço efetivo. A nota passa a ser o *ground truth* do preço de tabela.

Isso não enfraquece o modelo dos três preços — **reforça**. Cada fonte passa a medir a grandeza que de fato observa:

- `estimado` vs `observado` → **erro do modelo**
- `observado` vs `tabela` → **desconto capturado** (promoção que você pegou)

**Alternativa rejeitada**

- *Ratear o desconto proporcionalmente entre os itens* — fabricaria informação inexistente e sujaria a série de preço com valores que nunca estiveram na gôndola.

**Nota conceitual**

O `Vl. Unit` cheio **não é um defeito** — é o preço de tabela, e preço de tabela é *melhor* para série histórica, porque promoção é transitória. *"Leite Tirol custa R$ 5,19 no Condor"* é o fato estável; os R$ 0,50 de desconto no biscoito foram um evento.

---

<a name="adr-017"></a>
## ADR-017 — Toda linha carrega sua origem

**Contexto**

O app rodou dois meses em produção antes de existir qualquer pipeline. Nesse período, dado de teste e dado real foram gravados **na mesma tabela, sem distinção possível**:

- `Feijão Cacau` — a mesma linha com `1 kg` a R$ 10 **e** `100 g` a R$ 5. Um dos dois é impossível.
- `Açúcar Caravelas R$ 3,19` — quatro linhas idênticas. Compras repetidas ou insert duplicado? **Sem a nota fiscal, não há como saber.**
- `Cebola` — `valor_unitario = 0`. Valor faltante mascarado de zero.

O problema não é a existência do lixo. É que **nada na linha diz de onde ela veio** — e em seis meses ninguém vai lembrar.

**Decisão**

Toda tabela ganha a coluna `origem`, tipada como enum:

| Valor | Significado | Confiança |
|---|---|---|
| `nfce` | Extraído da nota fiscal | **Verdade** (ground truth) |
| `manual` | Digitado no app | Estimativa |
| `legado` | Histórico anterior à migração | Baixa |
| `teste` | Lixo de desenvolvimento | **Excluir de toda análise** |
| `seed` | Dado sintético do demo | Nunca misturar com real |

Enum, não `TEXT` livre — senão o próprio campo criado para resolver o problema de normalização passa a ter `'teste'`, `'TESTE'`, `'test'`, `'tst'`.

**Consequências**

1. **Filtro trivial no pipeline** — `WHERE origem <> 'teste'`. A dúvida deixa de existir.
2. **Confiança diferenciada no modelo** — preço vindo da NFC-e e preço digitado à mão são qualidades diferentes e não podem pesar igual.
3. **Seed sintético para o portfólio** — o recrutador roda o projeto com `origem = 'seed'`, vê tudo funcionando, e nenhum dado real é exposto.
4. É **linhagem de dados no nível da linha**. Barato de implementar, raro de encontrar.

**Regra associada: dado de teste é marcado, nunca deletado.**

A linha de teste vira **caso de teste do pipeline**: *"o filtro de origem funciona? Prove."* Deletar destrói a evidência.

**Causa raiz**

Os testes foram feitos **em produção** — não havia ambiente separado. A correção estrutural é um Postgres local em Docker (`docker-compose up`), que também é requisito do portfólio: o recrutador precisa conseguir rodar o projeto. Um arquivo resolve os dois problemas.

**Lição de execução: a ordem da migração importa**

A primeira tentativa aplicou colunas e *constraints* no mesmo script. Falhou:

```
ERROR: 23514: check constraint "chk_valor_positivo"
of relation "historico_compras" is violated by some row
```

Postgres roda DDL em transação — a constraint falhou contra o dado legado (a `Cebola` com preço zero) e **abortou a migração inteira**. Nem as colunas foram criadas.

Sequência correta:

```
1. diagnosticar o lixo
2. limpar (zero → NULL)
3. migrar estrutura
4. trancar com constraints
```

**A tentação errada seria afrouxar a constraint para a migração passar.** É assim que o lixo entra para sempre. Zero **não é** preço: "de graça" e "não sei quanto foi" são coisas diferentes, e `NULL` é a única forma honesta de dizer a segunda.

---

<a name="adr-018"></a>
## ADR-018 — Nunca armazenar o que pode ser derivado

**Contexto**

`sessoes_compra.valor_calculado` era mantido por incremento, no cliente:

```js
.update({ valor_calculado: (sessaoAtiva.valor_calculado || 0) + total })
```

Isso é um **read-modify-write**, e produziu dois bugs:

1. **Lost update** — duas pessoas marcando itens ao mesmo tempo (corredores diferentes do mercado) sobrescrevem uma à outra. O total fica errado **em silêncio**.
2. **Acumulação de erro em ponto flutuante** — os valores no banco incluem `233.01999999999998` e `122.14999999999999`. É soma de `float` em JavaScript, reescrita a cada item.

**Decisão**

Não armazenar o total. **Derivar:**

```sql
SELECT sessao_id, sum(valor_total) AS valor_calculado
FROM historico_compras
GROUP BY sessao_id;
```

O Postgres soma em `numeric` (aritmética decimal exata), no servidor, sem condição de corrida.

**Consequências**

- Elimina o *lost update* **por construção** — não há estado duplicado para divergir.
- Elimina o erro de float.
- Uma fonte da verdade: os itens. O total é uma **função** deles, não um fato independente.

> **Estado duplicado é estado que vai divergir.** Se um número pode ser calculado a partir de outros, calcule-o.

---

<a name="adr-019"></a>
## ADR-019 — Deflacionar, não prever: IPCA por subitem e índice de Laspeyres

**Contexto**

Como usar dados de inflação (IBGE) no projeto? A sugestão inicial era ajustar preços com Prophet.

**Decisão**

**Prophet está fora.** Três razões:

1. **Na série pessoal, é inviável** — 6 a 12 observações por produto. Prophet precisa de vários ciclos sazonais. Com 12 pontos ruidosos, ele ajusta **ruído** e devolve uma banda de confiança larga que *parece* rigorosa e não é.

2. **Na série do IPCA, é o modelo errado** — Prophet é um GAM que decompõe tendência + sazonalidade + feriados e extrapola. **Inflação é movida por choques exógenos** (câmbio, commodities, tarifas, política monetária). Prophet não enxerga nada disso: pega a tendência recente e a estica. É extrapolação ingênua com aparência de ciência.

3. **E o argumento que encerra:** o Banco Central publica o **boletim Focus** — expectativa de IPCA de centenas de instituições, semanal, com API pública e gratuita (Olinda/BCB).

   > Por que construir uma previsão **pior** do que uma que já existe de graça?

   Usar o Focus **é mais impressionante que fitar Prophet**: mostra conhecimento de domínio. Fitar Prophet mostra que se sabe chamar `.fit()`.

**O que é feito no lugar**

### 1. Deflacionar, não prever

O uso real do IPCA no app é:

```
preço esperado hoje = último preço pago × IPCA acumulado desde então
```

Isso **não é previsão** — é ajuste. Zero modelo. Resolve o item que não aparece na lista há três meses.

### 2. IPCA por **subitem**, não o índice cheio

O SIDRA/IBGE publica o IPCA desagregado: *"leite longa vida"*, *"arroz"*, *"café moído"*, *"carne bovina"*.

Corrigir o preço do leite pelo IPCA cheio — que inclui aluguel, gasolina e passagem aérea — é grosseiro. **Corrigir pelo subitem correspondente é preciso.**

### 3. Índice de Laspeyres doméstico — o trabalho estatístico de verdade

O IPCA é um **índice de Laspeyres**: cesta fixa, preços variáveis. O projeto tem os dois ingredientes:

- os **preços** (das notas fiscais)
- as **quantidades** (o que de fato se compra)

Portanto: **construir o índice de preços da própria casa** e compará-lo ao oficial.

> *"A inflação desta casa foi 7,2% em 12 meses. O IPCA-Alimentação foi 5,1%. A diferença: minha cesta é mais concentrada em proteína, que subiu mais."*

Comparar **Laspeyres** (cesta base) com **Paasche** (cesta atual) revela o **efeito substituição** — quanto se economizou trocando de produto quando os preços subiram. É o ADR-012 fechando o ciclo.

### 4. Prophet como benchmark derrotado

Se for para mostrar domínio de Prophet, o modo correto é **rodá-lo como baseline e demonstrar que ele perde**:

```
Modelo                            MAE      MAPE
──────────────────────────────────────────────
Naive (último preço)             0,42     6,1%
Mediana móvel + IPCA subitem     0,31     4,4%   ← vencedor
Prophet                          0,58     8,7%   ← perdeu
```

Com a conclusão escrita: *"Prophet perde para o baseline porque a série tem ~12 pontos e nenhuma sazonalidade estável."*

> Isso demonstra que se **avalia** modelos, em vez de assumi-los. É a diferença entre usar ferramenta e escolher ferramenta.

**Onde Prophet ou SARIMA teriam cabimento:** a série da ANP (semanal, milhares de pontos, sazonalidade real). Mas ela não serve ao propósito do app — seria modelo procurando problema.

---

# Erros cometidos e corrigidos

Esta seção existe de propósito. A evolução do modelo é o registro mais honesto do processo.

| # | Erro inicial | Correção | Como foi descoberto |
|---|---|---|---|
| 1 | Usar a API do Menor Preço | Fonte própria (NFC-e) | Leitura do Termo de Uso |
| 2 | Assumir GTIN na nota | Chave composta `(CNPJ, código)` | Spike da nota real |
| 3 | Contagem manual de despensa | Consumo derivado da lista | A tabela `produtos` terminou com 4 registros em 2 meses de uso real |
| 4 | Consumo = intervalo entre adições | Consumo = **taxa** em unidade base | Caso "2 cartelas duram o dobro" |
| 5 | Preço como dimensão SCD2 | Preço é **fato**; SCD2 é para embalagem | Revisão de modelagem |
| 6 | Flag de recorrência por evento | Recorrência é atributo do **produto** | Fricção de UX no uso real |
| 7 | Ignorar antecipação da lista | Captura do rótulo (dado censurado) | Caso "adiciono 2 dias antes" |
| 8 | Erro do modelo sem decompor | Decomposição preço × mix × volume | Caso "troquei de marca" |
| 9 | Desconto só no total | `Vl. Unit` é **preço de tabela**; desconto é por item | Comparação cupom de papel × consulta HTML |
| 10 | Constraints junto com a migração | Diagnosticar → limpar → migrar → trancar | Rollback total da migração |
| 11 | Soft delete ausente na lista | `arquivado = true` em vez de `DELETE` | Auditoria de código: o botão "limpar" apagava o sinal de consumo |
| 12 | Prophet para inflação | Focus + IPCA por subitem + Laspeyres | Revisão de adequação do modelo |

> Nenhum desses erros foi encontrado por revisão de código isolada. **Todos apareceram ao confrontar o modelo com o comportamento real do usuário e com o dado real.** É esse o argumento a favor de construir a plataforma sobre um problema que se vive, e não sobre um dataset do Kaggle.

---

## Pendências

- [x] Consolidar SQL com as correções dos ADRs 005, 006, 009, 011 e 016
- [ ] Implementar o parser da NFC-e com higienização de PII (ADR-006)
- [ ] `dim_apelido`: dicionário curado do vocabulário doméstico (dbt seed)
- [ ] Migrar credenciais do frontend para variáveis de ambiente
- [ ] `docker-compose.yml` — ambiente local, encerrando o "testar em produção" (ADR-017)
