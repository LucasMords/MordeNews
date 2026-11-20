"""Coletores de páginas HTML abertas.

`ColetorIEL`: mural de estágios do IEL (carreiras.iel.org.br). A fonte aponta para a página
do estado, por exemplo `https://carreiras.iel.org.br/TO`. O coletor:

1. lê o sitemap.xml oficial do site (o robots.txt permite tudo, menos /api/, que não usamos);
2. fica só com as vagas do estado (`/TO/vaga/...`) alteradas dentro da janela da fonte;
3. baixa a página das vagas que ainda não estão no banco e monta o texto com os campos
   rotulados da página (Empresa, Cidade, Remuneração...).

O site não informa data de publicação; usamos o `lastmod` do sitemap no lugar.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from radar import banco
from radar.coletores.base import Coletor, agora_utc
from radar.coletores.http import ClienteHttp
from radar.modelos import Fonte, Item, gerar_id_unico

log = logging.getLogger(__name__)

_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_ESPACOS = re.compile(r"\s+")

# Rótulos da página de vaga, na ordem em que aparecem. O texto vai até o próximo rótulo.
ROTULOS = (
    "Cód.",
    "Empresa:",
    "Atividades:",
    "Requisitos:",
    "Cursos:",
    "Escolaridade:",
    "Cidade:",
    "Remuneração:",
    "Benefícios:",
    "Horários:",
    "Formato de trabalho:",
)
_FIM_DA_VAGA = ("Faça login e se candidate", "Compartilhe nas redes sociais")


class ErroIEL(RuntimeError):
    """Sitemap ou página de vaga em formato inesperado."""


@dataclass(frozen=True)
class EntradaSitemap:
    url: str
    alterado_em: datetime | None


def _data(bruta: str | None) -> datetime | None:
    if not bruta:
        return None
    try:
        return datetime.fromisoformat(bruta.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def ler_sitemap(conteudo: bytes, prefixo: str) -> list[EntradaSitemap]:
    """Entradas do sitemap cujo caminho começa com `prefixo` (ex.: "/TO/vaga/")."""
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as erro:
        raise ErroIEL(f"sitemap ilegível: {erro}") from erro
    entradas = []
    for url in raiz.findall("s:url", _NS):
        loc = (url.findtext("s:loc", default="", namespaces=_NS) or "").strip()
        if urlsplit(loc).path.startswith(prefixo):
            lastmod = url.findtext("s:lastmod", default=None, namespaces=_NS)
            entradas.append(EntradaSitemap(loc, _data(lastmod)))
    return entradas


def ler_vaga(html: str) -> tuple[str, str]:
    """Extrai (título, texto) da página de uma vaga. O texto lista os campos rotulados."""
    sopa = BeautifulSoup(html, "html.parser")
    for tag in sopa(["script", "style", "noscript"]):
        tag.decompose()
    titulo_tag = sopa.find("h1")
    titulo = titulo_tag.get_text(" ", strip=True) if titulo_tag else ""
    if not titulo and sopa.title:
        titulo = sopa.title.get_text(strip=True).split("|")[0].strip()

    linhas = [_ESPACOS.sub(" ", t).strip() for t in sopa.get_text("\n").splitlines()]
    linhas = [t for t in linhas if t]
    campos: list[tuple[str, list[str]]] = []
    atual: list[str] | None = None
    for linha in linhas:
        if linha in _FIM_DA_VAGA:
            break
        if linha in ROTULOS:
            atual = []
            campos.append((linha.rstrip(":").rstrip("."), atual))
        elif atual is not None:
            atual.append(linha)
    if not titulo or not campos:
        raise ErroIEL("página de vaga sem título ou sem campos reconhecidos")
    texto = "\n".join(f"{rotulo}: {' '.join(valor)}" for rotulo, valor in campos if valor)
    return titulo, texto


class ColetorIEL(Coletor):
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
        partes = urlsplit(self.fonte.url)
        origem = f"{partes.scheme}://{partes.netloc}"
        prefixo = f"{partes.path.rstrip('/')}/vaga/"
        entradas = ler_sitemap(self.http.get(f"{origem}/sitemap.xml").content, prefixo)
        novas = [e for e in self._recentes(entradas) if not self._ja_coletada(e.url)]
        log.info(
            "%s: %d vagas no sitemap, %d novas na janela", self.nome, len(entradas), len(novas)
        )

        itens: list[Item] = []
        falhas = 0
        for entrada in novas:
            try:
                titulo, texto = ler_vaga(self.http.get(entrada.url).text)
            except Exception as erro:  # uma página ruim não derruba as outras
                falhas += 1
                log.warning("%s: vaga %s ignorada — %s", self.nome, entrada.url, erro)
                continue
            itens.append(
                Item(
                    modulo=self.fonte.modulo,
                    fonte=self.nome,
                    titulo=titulo,
                    url=entrada.url,
                    publicado_em=entrada.alterado_em,
                    texto=texto,
                )
            )
        if novas and falhas == len(novas):
            raise ErroIEL(f"nenhuma das {falhas} páginas de vaga pôde ser lida")
        return itens

    def _recentes(self, entradas: list[EntradaSitemap]) -> list[EntradaSitemap]:
        corte = self._agora() - timedelta(hours=self.fonte.janela_horas)
        dentro = [e for e in entradas if e.alterado_em is None or e.alterado_em >= corte]
        dentro.sort(key=lambda e: e.alterado_em or corte, reverse=True)
        return dentro[: self.fonte.limite]

    def _ja_coletada(self, url: str) -> bool:
        """Evita baixar de novo a página de uma vaga que já está no banco."""
        try:
            return self._conhecido(gerar_id_unico(url))
        except banco.ErroBanco as erro:
            log.warning(
                "%s: não foi possível consultar o banco (%s); baixando assim mesmo", self.nome, erro
            )
            return False
