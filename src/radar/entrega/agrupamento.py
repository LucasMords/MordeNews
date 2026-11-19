"""Agrupa a mesma notícia vinda de fontes diferentes, com regras determinísticas (sem IA).

Dois itens são o mesmo assunto quando:
- ambos citam CVEs e têm pelo menos um em comum (CVEs diferentes = falhas diferentes); ou
- ao menos um não cita CVE e:
  - os títulos compartilham um "nome" com letras e números (ex.: java4shell, log4shell); ou
  - os títulos têm ao menos MIN_COMUNS palavras significativas em comum, cobrindo
    LIMIAR_TITULO das palavras do título mais curto.
A relação é transitiva (A~B e B~C → A, B e C juntos).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime

from radar.entrega.correio import Assunto
from radar.modelos import ItemResumo

LIMIAR_TITULO = 0.6
MIN_COMUNS = 2
_CVE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
_PALAVRA = re.compile(r"[a-z0-9]+")

# Palavras frequentes que não ajudam a identificar o assunto (PT e EN), já sem acento.
_VAZIAS = frozenset(
    """
    a o as os um uma uns umas de da do das dos em no na nos nas por para pra com sem sobre
    e ou que se ao aos como mais menos ja nao sim seu sua seus suas pode podem novo nova novos
    novas apos ate entre the an of to in on for with and or by from at is are was be as its it
    new how why what your you this that after into over now not can will when where which who
    has have had about all just out its their they our
    """.split()  # noqa: SIM905 — lista longa fica mais legível como texto
)


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )


def palavras(titulo: str) -> frozenset[str]:
    """Palavras significativas do título: minúsculas, sem acento, sem palavras vazias."""
    return frozenset(
        p for p in _PALAVRA.findall(_sem_acento(titulo)) if len(p) >= 3 and p not in _VAZIAS
    )


def nomes(titulo: str) -> frozenset[str]:
    """Palavras com letras e números (5+ caracteres), típicas de nomes próprios de falhas e
    produtos: java4shell, log4shell, base64. São quase uma assinatura do assunto."""
    return frozenset(
        p
        for p in palavras(titulo)
        if len(p) >= 5 and any(c.isdigit() for c in p) and any(c.isalpha() for c in p)
    )


def cves(item: ItemResumo) -> frozenset[str]:
    return frozenset(c.upper() for c in _CVE.findall(f"{item.titulo} {item.resumo or ''}"))


def _parecidos(a: frozenset[str], b: frozenset[str]) -> bool:
    """Ao menos MIN_COMUNS palavras em comum, cobrindo LIMIAR_TITULO do título mais curto."""
    comuns = len(a & b)
    if comuns < MIN_COMUNS:
        return False
    return comuns / min(len(a), len(b)) >= LIMIAR_TITULO


def _ordem(item: ItemResumo) -> tuple[int, datetime, int]:
    return (item.nota, item.publicado_em or datetime.min.replace(tzinfo=UTC), item.id)


def agrupar(itens: Sequence[ItemResumo]) -> list[Assunto]:
    """Devolve um Assunto por notícia distinta, com o item de maior nota como principal.

    Itens de módulos diferentes nunca são agrupados. A lista sai ordenada por nota.
    """
    pais = list(range(len(itens)))

    def raiz(i: int) -> int:
        while pais[i] != i:
            pais[i] = pais[pais[i]]
            i = pais[i]
        return i

    titulos = [palavras(i.titulo) for i in itens]
    proprios = [nomes(i.titulo) for i in itens]
    codigos = [cves(i) for i in itens]
    for a in range(len(itens)):
        for b in range(a + 1, len(itens)):
            if itens[a].modulo != itens[b].modulo:
                continue
            if codigos[a] and codigos[b]:
                # Os dois citam CVEs: só são o mesmo assunto se for a mesma falha. Títulos de
                # segurança repetem jargão ("falha crítica permite execução remota").
                mesmo = bool(codigos[a] & codigos[b])
            else:
                mesmo = bool(proprios[a] & proprios[b]) or _parecidos(titulos[a], titulos[b])
            if mesmo:
                pais[raiz(b)] = raiz(a)

    grupos: dict[int, list[ItemResumo]] = {}
    for indice, item in enumerate(itens):
        grupos.setdefault(raiz(indice), []).append(item)

    assuntos = []
    for membros in grupos.values():
        membros.sort(key=_ordem, reverse=True)
        principal, *repetidos = membros
        assuntos.append(Assunto(principal, tuple(repetidos)))
    assuntos.sort(key=lambda a: _ordem(a.principal), reverse=True)
    return assuntos
