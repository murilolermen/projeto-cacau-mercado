import pytest

from extract.nfce.chave_acesso import ChaveAcesso

CHAVE_VALIDA = "41260776189406001955651130004070661004703656"


def test_parse_decompoe_todos_os_campos():
    chave = ChaveAcesso.parse(CHAVE_VALIDA)

    assert chave.uf == "41"
    assert chave.competencia == "2607"
    assert chave.cnpj_emitente == "76189406001955"
    assert chave.modelo == "65"
    assert chave.serie == "113"
    assert chave.numero == "000407066"


def test_dv_invalido_levanta_erro():
    chave_adulterada = CHAVE_VALIDA[:-1] + "0"  # último dígito trocado
    with pytest.raises(ValueError):
        ChaveAcesso.parse(chave_adulterada)


def test_tamanho_errado_levanta_erro():
    with pytest.raises(ValueError):
        ChaveAcesso.parse("123")
