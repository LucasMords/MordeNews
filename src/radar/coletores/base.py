"""Classe base dos coletores e a função comum `executar()`.

Cada coletor só implementa `buscar()`. Deduplicação, gravação e registro em `execucoes`
ficam em `executar()`, que nunca deixa a falha de um coletor derrubar os demais.
"""

from __future__ import annotations

import logging
import re
import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

from radar import banco
from radar.coletores.http import ClienteHttp
from radar.modelos import Fonte, Item

log = logging.getLogger(__name__)

_ESPACOS = re.compile(r"\s+")


def limpar_html(html: str) -> str:
    """Remove tags HTML e normaliza espaços."""
    if not html:
        return ""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MarkupResemblesLocatorWarning)
        sopa = BeautifulSoup(html, "html.parser")
    for tag in sopa(["script", "style", "noscript"]):
        tag.decompose()
    texto = sopa.get_text(" ")
    return _ESPACOS.sub(" ", texto).strip()


def agora_utc() -> datetime:
    return datetime.now(UTC)


class Coletor(ABC):
    def __init__(
        self,
        fonte: Fonte,
        http: ClienteHttp,
        agora: Callable[[], datetime] = agora_utc,
    ) -> None:
        self.fonte = fonte
        self.http = http
        self._agora = agora

    @property
    def nome(self) -> str:
        return self.fonte.nome

    @abstractmethod
    def buscar(self) -> list[Item]:
        """Busca os itens recentes da fonte, já normalizados."""

    def recentes(self, itens: Iterable[Item]) -> list[Item]:
        """Aplica a janela de tempo e o limite da fonte, dos mais novos para os mais antigos.

        Itens sem data são mantidos (a deduplicação evita que se repitam).
        """
        corte = self._agora() - timedelta(hours=self.fonte.janela_horas)
        dentro = [i for i in itens if i.publicado_em is None or i.publicado_em >= corte]
        minimo = datetime.min.replace(tzinfo=UTC)
        dentro.sort(key=lambda i: i.publicado_em or minimo, reverse=True)
        return dentro[: self.fonte.limite]


@dataclass(frozen=True)
class ResultadoColeta:
    coletor: str
    ok: bool
    encontrados: int = 0
    novos: int = 0
    erro: str | None = None


def executar(coletor: Coletor) -> ResultadoColeta:
    """Roda um coletor, grava os itens novos e registra a execução. Nunca propaga exceções."""
    iniciado_em = agora_utc()
    try:
        itens = coletor.buscar()
        novos = banco.salvar_itens(itens)
        resultado = ResultadoColeta(coletor.nome, ok=True, encontrados=len(itens), novos=novos)
        log.info("%s: %d itens recentes, %d novos", coletor.nome, len(itens), novos)
    except Exception as erro:
        descricao = f"{type(erro).__name__}: {erro}"
        resultado = ResultadoColeta(coletor.nome, ok=False, erro=descricao)
        log.error("%s: falhou — %s", coletor.nome, descricao)

    try:
        banco.registrar_execucao(
            coletor.nome,
            iniciado_em=iniciado_em,
            ok=resultado.ok,
            itens_novos=resultado.novos,
            erro=resultado.erro,
        )
    except banco.ErroBanco as erro:
        log.error("%s: não foi possível registrar a execução — %s", coletor.nome, erro)
    return resultado
