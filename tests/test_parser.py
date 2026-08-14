from datetime import datetime
from decimal import Decimal
from pathlib import Path

from extract.nfce.parser import parse_nota

FIXTURE = Path(__file__).parent / "fixtures" / "nota_exemplo.html"


def _nota():
    return parse_nota(FIXTURE.read_text(encoding="utf-8"))


def test_campos_da_nota():
    nota = _nota()

    assert nota.chave_acesso == "41260776189406001955651130004070661004703656"
    assert nota.cnpj_emitente == "76189406001955"
    assert nota.numero_nota == "407066"
    assert nota.serie_nota == "113"
    assert nota.data_emissao == datetime(2026, 7, 17, 20, 17, 20)
    assert nota.valor_total_nota == Decimal("29.88")
    assert nota.desconto_total is None  # esta nota de exemplo não tem desconto


def test_itens_da_nota():
    nota = _nota()

    assert len(nota.itens) == 2

    item = nota.itens[0]
    assert item.item_seq == 1
    assert item.codigo_interno == "1292424"
    assert item.descricao == "LINGUICA FRIMESA TOSCANA RESF.KG"
    assert item.quantidade == Decimal("0.774")
    assert item.unidade == "KG"
    assert item.valor_unitario_tabela == Decimal("19.97")
    assert item.valor_total_item_tabela == Decimal("15.46")


def test_html_bruto_nao_contem_dado_do_consumidor():
    """ADR-006: o payload gravado em raw não pode conter CPF/nome, mesmo
    tendo entrado no HTML original."""
    nota = _nota()

    # "Consumidor" sozinho aparece legitimamente em outros lugares do HTML
    # (ex: "Via Consumidor" na seção de emissão) — o que precisa sumir é
    # a seção <h4>Consumidor</h4> com CPF/nome, não a palavra em si.
    assert "<h4>Consumidor</h4>" not in nota.html_bruto
    assert "CPF" not in nota.html_bruto
    assert "000.000.000-00" not in nota.html_bruto
    assert "FULANO" not in nota.html_bruto
