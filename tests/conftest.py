"""Fixtures compartilhadas. Nenhum teste acessa a rede."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from typing import Any

import httpx
import pytest

from radar import banco
from radar.coletores.http import ClienteHttp
from radar.modelos import Fonte


class SupabaseFalso:
    """Imita o mínimo do PostgREST que o banco.py usa, guardando as tabelas em memória."""

    def __init__(self) -> None:
        self.tabelas: dict[str, list[dict[str, Any]]] = {"itens": [], "execucoes": []}
        self.requisicoes: list[httpx.Request] = []
        self._ids = count(1)
        self._inicio = datetime.now(UTC)
        self.falhar_com: int | None = None

    # --------------------------------------------------------- filtros
    @staticmethod
    def _filtros(params: httpx.QueryParams) -> list[tuple[str, str, str]]:
        reservados = {"select", "limit", "order", "on_conflict"}
        filtros = []
        for chave, valor in params.multi_items():
            if chave in reservados:
                continue
            operador, _, alvo = valor.partition(".")
            filtros.append((chave, operador, alvo))
        return filtros

    @staticmethod
    def _bate(linha: dict[str, Any], filtros: list[tuple[str, str, str]]) -> bool:
        for coluna, operador, alvo in filtros:
            valor = linha.get(coluna)
            texto = str(valor).lower() if isinstance(valor, bool) else str(valor)
            if operador == "eq" and texto != alvo:
                return False
            if operador == "neq" and texto == alvo:
                return False
            opcoes = [o.strip('"') for o in alvo.strip("()").split(",")]
            if operador == "in" and texto not in opcoes:
                return False
            if operador == "is" and alvo == "null" and valor is not None:
                return False
            if operador == "not" and alvo == "is.null" and valor is None:
                return False
            if operador == "gte" and (valor is None or not SupabaseFalso._maior_igual(valor, alvo)):
                return False
            if operador == "lt" and (valor is None or SupabaseFalso._maior_igual(valor, alvo)):
                return False
        return True

    @staticmethod
    def _maior_igual(valor: Any, alvo: str) -> bool:
        if isinstance(valor, int | float):
            return valor >= float(alvo)
        return str(valor) >= alvo  # datas ISO comparam bem como texto

    @staticmethod
    def _selecionar(linha: dict[str, Any], select: str | None) -> dict[str, Any]:
        if not select or select == "*":
            return dict(linha)
        return {c: linha.get(c) for c in select.split(",")}

    # -------------------------------------------------------- handler
    def __call__(self, requisicao: httpx.Request) -> httpx.Response:
        self.requisicoes.append(requisicao)
        if self.falhar_com:
            return httpx.Response(self.falhar_com, json={"message": "erro simulado"})

        tabela = requisicao.url.path.rsplit("/", 1)[-1]
        linhas = self.tabelas[tabela]
        params = requisicao.url.params
        filtros = self._filtros(params)
        prefer = requisicao.headers.get("Prefer", "")

        if requisicao.method == "GET":
            achadas = [linha for linha in linhas if self._bate(linha, filtros)]
            ordem = params.get("order")
            if ordem:
                # ordena da última chave para a primeira (sort estável = ordenação composta)
                for criterio in reversed(ordem.split(",")):
                    coluna, _, direcao = criterio.partition(".")
                    achadas.sort(
                        key=lambda linha, c=coluna: (linha.get(c) is not None, linha.get(c) or 0),
                        reverse=direcao.startswith("desc"),
                    )
            if "limit" in params:
                achadas = achadas[: int(params["limit"])]
            return httpx.Response(
                200, json=[self._selecionar(a, params.get("select")) for a in achadas]
            )

        if requisicao.method == "POST":
            corpo = json.loads(requisicao.content)
            novas = corpo if isinstance(corpo, list) else [corpo]
            conflito = params.get("on_conflict")
            inseridas = []
            for nova in novas:
                if conflito and any(linha.get(conflito) == nova.get(conflito) for linha in linhas):
                    if "ignore-duplicates" in prefer:
                        continue
                    return httpx.Response(409, json={"message": "duplicate key"})
                novo_id = next(self._ids)
                padrao = {
                    "id": novo_id,
                    "status": "pendente",
                    "tentativas_ia": 0,
                    # hora real + id: mantém a ordem de inserção e funciona com janelas relativas
                    "coletado_em": (self._inicio + timedelta(seconds=novo_id)).isoformat(),
                }
                linha = {**padrao, **nova}
                linhas.append(linha)
                inseridas.append(linha)
            if "return=representation" in prefer:
                select = params.get("select")
                return httpx.Response(201, json=[self._selecionar(i, select) for i in inseridas])
            return httpx.Response(201)

        if requisicao.method == "PATCH":
            mudancas = json.loads(requisicao.content)
            alteradas = [linha for linha in linhas if self._bate(linha, filtros)]
            for linha in alteradas:
                linha.update(mudancas)
            if "return=representation" in prefer:
                select = params.get("select")
                return httpx.Response(200, json=[self._selecionar(a, select) for a in alteradas])
            return httpx.Response(204)

        if requisicao.method == "DELETE":
            self.tabelas[tabela] = [linha for linha in linhas if not self._bate(linha, filtros)]
            return httpx.Response(204)

        return httpx.Response(405)


FIXTURES = Path(__file__).parent / "fixtures"
AGORA = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def ler_fixture(nome: str) -> bytes:
    return (FIXTURES / nome).read_bytes()


class SiteFalso:
    """Transporte httpx que serve respostas fixas por URL e registra o que foi pedido.

    URLs de robots.txt não cadastradas respondem 404 (o que libera a coleta).
    """

    def __init__(self, rotas: dict[str, httpx.Response | Exception] | None = None) -> None:
        self.rotas = dict(rotas or {})
        self.pedidos: list[httpx.Request] = []

    def __call__(self, requisicao: httpx.Request) -> httpx.Response:
        self.pedidos.append(requisicao)
        url = str(requisicao.url)
        if url in self.rotas:
            resposta = self.rotas[url]
            if isinstance(resposta, Exception):
                raise resposta
            return resposta
        if requisicao.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(404, text="não encontrado")

    def urls(self) -> list[str]:
        return [str(p.url) for p in self.pedidos]


def cliente_http(site: SiteFalso, **opcoes: Any) -> ClienteHttp:
    opcoes.setdefault("pausa", 0)
    return ClienteHttp("RadarPessoal/0.1 (+teste)", transporte=httpx.MockTransport(site), **opcoes)


def fonte(**extra: Any) -> Fonte:
    dados: dict[str, Any] = {
        "modulo": "noticias",
        "nome": "exemplo",
        "tipo": "rss",
        "url": "https://blog.exemplo.com/feed",
    }
    dados.update(extra)
    return Fonte.model_validate(dados)


@pytest.fixture
def supabase() -> Iterator[SupabaseFalso]:
    falso = SupabaseFalso()
    cliente = httpx.Client(
        base_url="https://falso.supabase.co/rest/v1",
        transport=httpx.MockTransport(falso),
        headers=banco._cabecalhos("sb_secret_teste"),
    )
    banco.definir_cliente(cliente)
    yield falso
    banco.definir_cliente(None)
    cliente.close()
