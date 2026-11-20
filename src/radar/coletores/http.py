"""Cliente HTTP compartilhado pelos coletores, com as regras de boa conduta do projeto.

- User-Agent identificável e timeout de 20s;
- pausa mínima entre requisições ao mesmo domínio;
- respeito ao robots.txt (lido uma vez por domínio e guardado em cache).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from radar import config

log = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 20.0
PAUSA_MESMO_DOMINIO = 1.5


class BloqueadoPorRobots(RuntimeError):
    """O robots.txt do site não permite coletar a URL."""


class ClienteHttp:
    def __init__(
        self,
        user_agent: str,
        *,
        transporte: httpx.BaseTransport | None = None,
        pausa: float = PAUSA_MESMO_DOMINIO,
        dormir: Callable[[float], None] = time.sleep,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.user_agent = user_agent
        self._http = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=TIMEOUT_SEGUNDOS,
            follow_redirects=True,
            transport=transporte,
        )
        self._pausa = pausa
        self._dormir = dormir
        self._relogio = relogio
        self._ultimo_acesso: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}

    def __enter__(self) -> ClienteHttp:
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    def fechar(self) -> None:
        self._http.close()

    def get(self, url: str, cabecalhos: dict[str, str] | None = None) -> httpx.Response:
        """GET respeitando robots.txt e a pausa por domínio. Erros HTTP viram exceção."""
        if not self.permitido(url):
            raise BloqueadoPorRobots(f"robots.txt de {urlsplit(url).netloc} não permite {url}")
        resposta = self._requisitar(url, cabecalhos)
        resposta.raise_for_status()
        return resposta

    def permitido(self, url: str) -> bool:
        partes = urlsplit(url)
        origem = f"{partes.scheme}://{partes.netloc}"
        if origem not in self._robots:
            self._robots[origem] = self._ler_robots(origem)
        return self._robots[origem].can_fetch(config.NOME_ROBO, url)

    def _ler_robots(self, origem: str) -> RobotFileParser:
        """Mesma política do urllib.robotparser: 401/403 bloqueiam tudo, outros 4xx liberam."""
        robots = RobotFileParser()
        try:
            resposta = self._requisitar(f"{origem}/robots.txt")
        except httpx.HTTPError as erro:
            log.warning(
                "robots.txt de %s inacessível (%s); pulando o domínio nesta rodada", origem, erro
            )
            robots.disallow_all = True
            return robots
        if resposta.status_code in (401, 403) or resposta.status_code >= 500:
            robots.disallow_all = True
        elif resposta.status_code >= 400:
            robots.allow_all = True
        else:
            robots.parse(resposta.text.splitlines())
        return robots

    def _requisitar(self, url: str, cabecalhos: dict[str, str] | None = None) -> httpx.Response:
        dominio = urlsplit(url).netloc
        ultimo = self._ultimo_acesso.get(dominio)
        if ultimo is not None:
            espera = self._pausa - (self._relogio() - ultimo)
            if espera > 0:
                self._dormir(espera)
        try:
            return self._http.get(url, headers=cabecalhos)
        finally:
            self._ultimo_acesso[dominio] = self._relogio()
