"""Coletor de vagas publicadas como issues em repositórios do GitHub (API REST oficial).

Comunidades como backend-br/vagas usam uma issue por vaga, com labels de nível,
modalidade e contrato. A fonte aponta para o repositório na API, por exemplo:
`https://api.github.com/repos/backend-br/vagas`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from radar import config
from radar.coletores.base import Coletor, limpar_html
from radar.modelos import Item

log = logging.getLogger(__name__)


class ErroGitHub(RuntimeError):
    """A resposta da API do GitHub não tem o formato esperado."""


def _data(bruta: str | None) -> datetime | None:
    if not bruta:
        return None
    return datetime.fromisoformat(bruta.replace("Z", "+00:00"))


def _texto(issue: dict[str, Any]) -> str:
    """Labels primeiro (nível, modalidade, contrato), depois o corpo da issue."""
    labels = [lb.get("name", "") for lb in issue.get("labels") or [] if isinstance(lb, dict)]
    labels = [nome for nome in labels if nome]
    corpo = limpar_html(issue.get("body") or "")
    return f"Labels: {', '.join(labels)}\n\n{corpo}" if labels else corpo


class ColetorGitHub(Coletor):
    def buscar(self) -> list[Item]:
        url = (
            f"{self.fonte.url.rstrip('/')}/issues"
            f"?state=open&sort=created&direction=desc&per_page={self.fonte.limite}"
        )
        resposta = self.http.get(url, self._cabecalhos())
        return self.recentes(self.interpretar(resposta.json()))

    @staticmethod
    def _cabecalhos() -> dict[str, str]:
        cabecalhos = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = config.carregar().github_token
        if token:  # sem token: 60 requisições/hora por IP, suficiente para uso local
            cabecalhos["Authorization"] = f"Bearer {token}"
        return cabecalhos

    def interpretar(self, dados: object) -> list[Item]:
        """Converte a lista de issues em Itens. Pull requests e issues sem link são ignorados."""
        if not isinstance(dados, list):
            raise ErroGitHub("resposta da API não é uma lista de issues")
        itens: list[Item] = []
        for issue in dados:
            if not isinstance(issue, dict) or "pull_request" in issue:
                continue
            titulo = (issue.get("title") or "").strip()
            url = (issue.get("html_url") or "").strip()
            if not titulo or not url.startswith("https://"):
                log.debug("%s: issue ignorada (sem título ou link)", self.nome)
                continue
            itens.append(
                Item(
                    modulo=self.fonte.modulo,
                    fonte=self.nome,
                    titulo=titulo,
                    url=url,
                    publicado_em=_data(issue.get("created_at")),
                    texto=_texto(issue),
                )
            )
        return itens
