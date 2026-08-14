"""Parser do DANFE HTML da NFC-e → NotaFiscal + itens (raw, ADR-004).

Estrutura confirmada contra uma nota real (fazenda.pr.gov.br/nfce/qrcode),
não deduzida — ver tests/fixtures/nota_exemplo.html.

Duas regras não-negociáveis aqui (ADR-006):
  1. CPF e nome do consumidor NUNCA saem deste módulo em nenhum campo.
  2. `html_bruto` (o payload guardado em raw, ver ADR-004) tem o bloco
     "Consumidor" removido antes de ser devolvido — não é só "não
     extraímos esses campos", é "o HTML gravado não contém mais isso".
"""
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from bs4 import BeautifulSoup

from extract.nfce.chave_acesso import ChaveAcesso


@dataclass(frozen=True)
class ItemNota:
    item_seq: int
    codigo_interno: str
    descricao: str
    quantidade: Decimal
    unidade: str
    valor_unitario_tabela: Decimal
    valor_total_item_tabela: Decimal


@dataclass(frozen=True)
class NotaFiscal:
    chave_acesso: str
    uf_emitente: str
    competencia: str
    cnpj_emitente: str
    numero_nota: str
    serie_nota: str
    data_emissao: datetime
    valor_total_nota: Decimal | None
    desconto_total: Decimal | None
    html_bruto: str  # já higienizado — sem o bloco Consumidor
    itens: list[ItemNota]


def parse_nota(html: str) -> NotaFiscal:
    soup = BeautifulSoup(html, "html.parser")

    # Primeiro de tudo, antes de qualquer outra leitura: remove o bloco
    # com CPF/nome. É o que vai virar `html_bruto` — se isso rodar depois,
    # ainda existe uma janela onde o dado sensível está "só não lido", não
    # "removido" (ADR-006 pede o segundo, não o primeiro).
    _remover_bloco_consumidor(soup)

    chave = _extrair_chave_acesso(soup)
    data_emissao = _extrair_data_emissao(soup)
    totais = _mapa_totais(soup)

    itens = [
        _parse_item(idx, tr)
        for idx, tr in enumerate(soup.select("#tabResult > tr"), start=1)
    ]

    return NotaFiscal(
        chave_acesso=chave.chave,
        uf_emitente=chave.uf,
        competencia=chave.competencia,
        cnpj_emitente=chave.cnpj_emitente,
        numero_nota=chave.numero.lstrip("0") or "0",
        serie_nota=chave.serie.lstrip("0") or "0",
        data_emissao=data_emissao,
        valor_total_nota=_valor_opcional(totais, "Valor a pagar R$"),
        # Rótulo exato ainda não confirmado contra uma nota real com
        # desconto — nenhuma das notas usadas até agora tinha promoção.
        # Revisar contra `totais` se este campo vier None num caso real.
        desconto_total=_valor_opcional(totais, "Desconto"),
        html_bruto=str(soup),
        itens=itens,
    )


def _remover_bloco_consumidor(soup: BeautifulSoup) -> None:
    for bloco in soup.select('div[data-role="collapsible"]'):
        titulo = bloco.find("h4")
        if titulo and titulo.get_text(strip=True) == "Consumidor":
            bloco.decompose()


def _extrair_chave_acesso(soup: BeautifulSoup) -> ChaveAcesso:
    span = soup.select_one("span.chave")
    if span is None:
        raise ValueError("HTML sem <span class='chave'> — não é um DANFE de NFC-e reconhecido")
    digitos = re.sub(r"\D", "", span.get_text())
    return ChaveAcesso.parse(digitos)


def _extrair_data_emissao(soup: BeautifulSoup) -> datetime:
    texto = soup.get_text()
    m = re.search(r"Emiss[aã]o:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})", texto)
    if m is None:
        raise ValueError("não encontrei a data de emissão no HTML")
    return datetime.strptime(m.group(1), "%d/%m/%Y %H:%M:%S")


def _mapa_totais(soup: BeautifulSoup) -> dict[str, str]:
    """{'Valor a pagar R$': '29,88', 'Qtd. total de itens': '2', ...}."""
    mapa = {}
    for div in soup.select('#totalNota div[id="linhaTotal"]'):
        rotulo = div.find("label")
        valor = div.find("span")
        if rotulo and valor:
            chave = rotulo.get_text(strip=True).rstrip(":")
            mapa[chave] = valor.get_text(strip=True)
    return mapa


def _valor_opcional(totais: dict[str, str], rotulo: str) -> Decimal | None:
    texto = totais.get(rotulo)
    return _brl_para_decimal(texto) if texto is not None else None


def _parse_item(item_seq: int, tr) -> ItemNota:
    descricao = tr.select_one("span.txtTit2").get_text(strip=True)

    m_codigo = re.search(r"C[oó]digo:\s*([^)]+)", tr.select_one("span.RCod").get_text())
    codigo_interno = m_codigo.group(1).strip()

    quantidade = _brl_para_decimal(_valor_apos_rotulo(tr.select_one("span.Rqtd")))
    unidade = _valor_apos_rotulo(tr.select_one("span.RUN"))
    valor_unitario = _brl_para_decimal(_valor_apos_rotulo(tr.select_one("span.RvlUnit")))
    valor_total = _brl_para_decimal(tr.select_one("span.valor").get_text(strip=True))

    return ItemNota(
        item_seq=item_seq,
        codigo_interno=codigo_interno,
        descricao=descricao,
        quantidade=quantidade,
        unidade=unidade,
        valor_unitario_tabela=valor_unitario,
        valor_total_item_tabela=valor_total,
    )


def _valor_apos_rotulo(span) -> str:
    """Nesses spans o valor é sempre o último nó de texto, depois do
    <strong> do rótulo (ex: <span><strong>UN: </strong>KG</span>)."""
    return str(span.contents[-1]).strip()


def _brl_para_decimal(texto: str) -> Decimal:
    return Decimal(texto.strip().replace(".", "").replace(",", "."))
