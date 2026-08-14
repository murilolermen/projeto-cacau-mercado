"""Parse e validação da chave de acesso da NFC-e (ADR-001).

A chave tem 44 dígitos, decompostos sem precisar de nenhuma requisição:
UF(2) AAMM(4) CNPJ(14) modelo(2) série(3) número(9) tpEmis(1) cNF(8) DV(1).

O DV (módulo 11) permite validar a integridade da chave ANTES de bater no
servidor da SEFA — é o primeiro teste de qualidade da camada raw.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ChaveAcesso:
    chave: str
    uf: str
    competencia: str  # AAMM de emissão
    cnpj_emitente: str
    modelo: str
    serie: str
    numero: str
    tp_emissao: str
    codigo_numerico: str
    dv: str

    @classmethod
    def parse(cls, chave: str) -> "ChaveAcesso":
        chave = chave.strip()
        if len(chave) != 44 or not chave.isdigit():
            raise ValueError(f"chave de acesso precisa ter 44 dígitos, recebido: {chave!r}")

        if not _dv_valido(chave):
            raise ValueError(f"dígito verificador inválido para a chave {chave!r}")

        return cls(
            chave=chave,
            uf=chave[0:2],
            competencia=chave[2:6],
            cnpj_emitente=chave[6:20],
            modelo=chave[20:22],
            serie=chave[22:25],
            numero=chave[25:34],
            tp_emissao=chave[34:35],
            codigo_numerico=chave[35:43],
            dv=chave[43:44],
        )


def _dv_valido(chave: str) -> bool:
    corpo, dv_informado = chave[:43], int(chave[43])

    # Módulo 11: peso começa em 2 e cicla até 9, aplicado da direita pra
    # esquerda. Resto < 2 vira DV 0; senão, DV = 11 - resto.
    soma = 0
    peso = 2
    for digito in reversed(corpo):
        soma += int(digito) * peso
        peso = peso + 1 if peso < 9 else 2

    resto = soma % 11
    dv_calculado = 0 if resto < 2 else 11 - resto
    return dv_informado == dv_calculado
