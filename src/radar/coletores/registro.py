"""Monta os coletores a partir das fontes do fontes.yaml."""

from __future__ import annotations

from collections.abc import Iterable

from radar.coletores.base import Coletor
from radar.coletores.github import ColetorGitHub
from radar.coletores.html import ColetorIEL
from radar.coletores.http import ClienteHttp
from radar.coletores.rss import ColetorRSS
from radar.modelos import Fonte

TIPOS: dict[str, type[Coletor]] = {
    "rss": ColetorRSS,
    "github": ColetorGitHub,
    "iel": ColetorIEL,
}


def montar_coletores(fontes: Iterable[Fonte], http: ClienteHttp) -> list[Coletor]:
    return [TIPOS[fonte.tipo](fonte, http) for fonte in fontes]


def filtrar_fontes(
    fontes: Iterable[Fonte], *, nomes: Iterable[str] = (), modulo: str | None = None
) -> list[Fonte]:
    """Seleciona fontes por nome e/ou módulo. Sem filtros, devolve todas."""
    escolhidos = set(nomes)
    return [
        f
        for f in fontes
        if (not escolhidos or f.nome in escolhidos) and (modulo is None or f.modulo == modulo)
    ]
