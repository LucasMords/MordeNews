"""Coletor de feeds RSS e Atom."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import feedparser

from radar.coletores.base import Coletor, limpar_html
from radar.modelos import Item

log = logging.getLogger(__name__)


class ErroFeed(RuntimeError):
    """O conteúdo baixado não é um feed legível."""


def _data(entrada: Any) -> datetime | None:
    estrutura: time.struct_time | None = entrada.get("published_parsed") or entrada.get(
        "updated_parsed"
    )
    if not estrutura:
        return None
    return datetime(*estrutura[:6], tzinfo=UTC)


def _texto(entrada: Any) -> str:
    conteudos = entrada.get("content") or []
    for conteudo in conteudos:
        if conteudo.get("value"):
            return limpar_html(conteudo["value"])
    return limpar_html(entrada.get("summary", ""))


class ColetorRSS(Coletor):
    def buscar(self) -> list[Item]:
        resposta = self.http.get(self.fonte.url)
        return self.recentes(self.interpretar(resposta.content))

    def interpretar(self, conteudo: bytes) -> list[Item]:
        """Converte o XML do feed em Itens, descartando entradas sem título ou link."""
        feed = feedparser.parse(conteudo)
        # Feed vazio mas válido é normal; página HTML ou XML quebrado no lugar do feed é erro.
        if not feed.entries and (feed.get("bozo") or not feed.get("version")):
            motivo = feed.get("bozo_exception") or "conteúdo não é RSS/Atom"
            raise ErroFeed(f"feed ilegível: {motivo}")

        itens: list[Item] = []
        for entrada in feed.entries:
            titulo = limpar_html(entrada.get("title", ""))
            url = (entrada.get("link") or "").strip()
            if not titulo or not url.startswith(("http://", "https://")):
                log.debug("%s: entrada ignorada (sem título ou link)", self.nome)
                continue
            itens.append(
                Item(
                    modulo=self.fonte.modulo,
                    fonte=self.nome,
                    titulo=titulo,
                    url=url,
                    publicado_em=_data(entrada),
                    texto=_texto(entrada),
                )
            )
        return itens
