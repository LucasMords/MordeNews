"""Coletores de feeds RSS e Atom."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import feedparser
from bs4 import BeautifulSoup

from radar import banco
from radar.coletores.base import Coletor, agora_utc, limpar_html
from radar.coletores.http import ClienteHttp
from radar.modelos import Fonte, Item

log = logging.getLogger(__name__)

_ESPACOS = re.compile(r"\s+")


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


# ------------------------------------------------------------ feed + página do artigo

# Frases que levam as informações do concurso. Vão para o começo do texto, porque a IA só
# recebe os primeiros caracteres (ia/cliente.py::LIMITE_TEXTO_IA).
_IMPORTANTE = re.compile(
    r"inscri|prazo|vaga|sal[aá]ri|vencimento|remunera|cargo|edital|prova|banca|taxa|escolaridade",
    re.IGNORECASE,
)
_RUIDO = frozenset(
    {"continua depois da publicidade", "seguir no google", "canal no whatsapp", "leia também"}
)


def ler_artigo(html: str, url: str = "") -> str:
    """Texto do artigo (parágrafos, títulos e listas), com as frases importantes primeiro.

    `url` é a página do artigo: links para o mesmo site não contam como link do edital.
    """
    sopa = BeautifulSoup(html, "html.parser")
    corpo = sopa.find("article") or sopa.find("main") or sopa.body
    if corpo is None:
        return ""
    for tag in corpo(["script", "style", "noscript", "aside", "nav", "form", "figure"]):
        tag.decompose()
    blocos: list[str] = []
    for el in corpo.find_all(["p", "li", "h2", "h3"]):
        texto = _ESPACOS.sub(" ", el.get_text(" ", strip=True)).strip()
        if len(texto) < 4 or texto.lower() in _RUIDO or texto in blocos:
            continue
        link = el.find("a")
        if el.name == "li" and link and link.get_text(" ", strip=True) == texto:
            continue  # lista de links ("Leia também"), não conteúdo
        blocos.append(texto)
    importantes = [b for b in blocos if _IMPORTANTE.search(b)]
    outros = [b for b in blocos if not _IMPORTANTE.search(b)]
    return "\n".join(_links_edital(corpo, urlsplit(url).netloc) + importantes + outros)


def _links_edital(corpo: Any, site: str) -> list[str]:
    """Links cujo texto cita o edital: o href some no texto puro, e a IA só pode usar links
    que estejam escritos no texto. Links para o próprio site (outros artigos, como "Concurso X
    abre edital") ficam de fora."""
    linhas: list[str] = []
    for link in corpo.find_all("a", href=True):
        href = link["href"].strip()
        externo = href.startswith("http") and urlsplit(href).netloc not in ("", site)
        if "edital" in link.get_text(" ", strip=True).lower() and externo:
            linha = f"Link do edital: {href}"
            if linha not in linhas:
                linhas.append(linha)
    return linhas[:3]


class ColetorRSSPagina(ColetorRSS):
    """Feed que traz só um trecho: abre a página do artigo de cada item novo."""

    def __init__(
        self,
        fonte: Fonte,
        http: ClienteHttp,
        agora: Callable[[], datetime] = agora_utc,
        conhecido: Callable[[str], bool] = banco.existe,
    ) -> None:
        super().__init__(fonte, http, agora)
        self._conhecido = conhecido

    def buscar(self) -> list[Item]:
        itens = super().buscar()
        completos = []
        for item in itens:
            if self._ja_coletado(item):
                completos.append(item)  # a deduplicação descarta; não precisa baixar de novo
                continue
            try:
                artigo = ler_artigo(self.http.get(item.url).text, item.url)
            except Exception as erro:  # sem a página, fica o trecho do feed
                log.warning("%s: página %s não lida — %s", self.nome, item.url, erro)
                artigo = ""
            if artigo:
                item = item.model_copy(update={"texto": f"{item.texto}\n{artigo}".strip()})
                item = Item.model_validate(item.model_dump())  # reaplica limpeza e truncamento
            completos.append(item)
        return completos

    def _ja_coletado(self, item: Item) -> bool:
        try:
            return self._conhecido(item.id_unico)
        except banco.ErroBanco as erro:
            log.warning("%s: banco indisponível (%s); baixando assim mesmo", self.nome, erro)
            return False
