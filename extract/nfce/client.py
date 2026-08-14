"""Busca o HTML do DANFE a partir do conteúdo lido no QR Code (ADR-001).

O QR da NFC-e do Paraná traz `chave|versão|ambiente|idToken|hash` no
parâmetro `p`. A URL resolvida responde com um `GET` simples — sem
captcha, sem login (confirmado no spike do ADR-001).
"""
import requests

BASE_URL = "https://www.fazenda.pr.gov.br/nfce/qrcode"

# O servidor derruba a conexão (RemoteDisconnected, sem resposta) quando o
# User-Agent é o default do `requests` ("python-requests/x.x"). Um
# User-Agent de navegador comum resolve — confirmado contra o site real.
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def buscar_html(conteudo_qr: str, timeout: int = 15) -> str:
    """`conteudo_qr` pode ser a URL completa lida da câmera, ou só o `p=...`."""
    url = conteudo_qr if conteudo_qr.startswith("http") else f"{BASE_URL}?p={conteudo_qr}"
    resposta = requests.get(url, headers=HEADERS, timeout=timeout)
    resposta.raise_for_status()
    return resposta.text
