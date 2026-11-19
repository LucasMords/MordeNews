"""Único ponto do projeto que chama um LLM (hoje, Gemini via SDK google-genai).

Trocar de fornecedor = reescrever só `_chamar_modelo` e `_cliente_genai`.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from radar import config
from radar.modelos import ItemPendente, Modulo, Resultado

log = logging.getLogger(__name__)

PASTA_PROMPTS = Path(__file__).parent / "prompts"
LIMITE_TEXTO_IA = 1500
MAX_RETENTATIVAS = 3
ESPERA_BASE_SEGUNDOS = 5.0
TIMEOUT_MS = 120_000

TAGS_NOTICIAS: tuple[str, ...] = (
    "dev", "backend", "java", "spring", "frontend", "javascript", "banco-de-dados",
    "arquitetura", "testes", "devops", "open-source", "ferramentas-dev", "ia", "agentes", "llm",
    "seguranca", "vulnerabilidade", "hardware", "redes", "sistemas-operacionais", "cloud",
    "certificacoes", "carreira", "vagas", "concursos", "educacao", "big-tech", "mercado",
    "regulacao", "privacidade", "ciencia", "brasil", "tocantins", "games", "outros",
)  # fmt: skip

TAGS_POR_MODULO: dict[str, tuple[str, ...]] = {"noticias": TAGS_NOTICIAS}


class ErroIA(RuntimeError):
    """Falha ao chamar o modelo (chave inválida, erro do servidor persistente etc.)."""


class CotaEsgotada(ErroIA):
    """O fornecedor recusou por cota (HTTP 429) mesmo após as retentativas."""


# ------------------------------------------------------------------ prompt


def carregar_prompt(modulo: Modulo) -> str:
    caminho = PASTA_PROMPTS / f"{modulo}.md"
    if not caminho.exists():
        raise config.ErroConfiguracao(f"Prompt do módulo '{modulo}' não encontrado: {caminho}")
    return caminho.read_text(encoding="utf-8")


def modulos_com_prompt() -> list[Modulo]:
    return [
        m for m in ("noticias", "estagios", "concursos") if (PASTA_PROMPTS / f"{m}.md").exists()
    ]


def montar_instrucoes(modulo: Modulo, perfil: str, hoje: date) -> str:
    return (
        f"{carregar_prompt(modulo).strip()}\n\n"
        f"Data de hoje: {hoje.isoformat()}\n\n"
        "## PERFIL DO USUÁRIO\n\n"
        f"{perfil.strip()}\n"
    )


SEM_TEXTO = "(a fonte não fornece texto; avalie pelo assunto do título, sem descartar por isso)"

# Itens do hnrss.org trazem só metadados:
# "Article URL: ... Comments URL: ... Points: N # Comments: M"
_METADADOS_HN = re.compile(
    r"^Article URL:\s*\S+\s+Comments URL:\s*\S+\s+Points:\s*(\d+)\s+#\s*Comments:\s*(\d+)\s*$"
)


def texto_para_ia(texto: str | None) -> str:
    """Primeiros 1.500 caracteres do texto, ou um aviso explícito quando não há conteúdo.

    Sem o aviso, o modelo tende a descartar itens que só têm título (ex.: Hacker News).
    """
    limpo = (texto or "").strip()
    hn = _METADADOS_HN.match(limpo)
    if hn:
        return f"{SEM_TEXTO} Pontos no Hacker News: {hn[1]}; comentários: {hn[2]}."
    if not limpo:
        return SEM_TEXTO
    return limpo[:LIMITE_TEXTO_IA]


def montar_conteudo(itens: Sequence[ItemPendente]) -> str:
    """Só id, título e os primeiros 1.500 caracteres do texto vão para a IA."""
    lista = [{"id": i.id, "titulo": i.titulo, "texto": texto_para_ia(i.texto)} for i in itens]
    return "Avalie estas notícias:\n" + json.dumps(lista, ensure_ascii=False)


def esquema_resposta(modulo: Modulo) -> dict[str, Any]:
    """JSON Schema da saída estruturada pedida ao modelo."""
    tags = TAGS_POR_MODULO.get(modulo)
    item_tag: dict[str, Any] = (
        {"type": "string", "enum": list(tags)} if tags else {"type": "string"}
    )
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "nota": {"type": "integer", "minimum": 0, "maximum": 10},
                "resumo": {"type": "string"},
                "tags": {"type": "array", "items": item_tag, "maxItems": 4},
                "descartar": {"type": "boolean"},
                "prazo": {"type": ["string", "null"], "format": "date"},
            },
            "required": ["id", "nota", "resumo", "tags", "descartar", "prazo"],
        },
    }


# --------------------------------------------------------------- resposta

_CERCA = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def interpretar_resposta(
    texto: str | None, ids_esperados: set[int], tags_validas: Sequence[str] | None = None
) -> list[Resultado]:
    """Valida a resposta da IA item a item. Itens inválidos, repetidos ou com id
    desconhecido são ignorados (e continuam pendentes)."""
    if not texto:
        log.warning("resposta da IA vazia")
        return []
    try:
        dados = json.loads(_CERCA.sub("", texto))
    except json.JSONDecodeError as erro:
        log.warning("resposta da IA não é JSON válido: %s", erro)
        return []
    if isinstance(dados, dict):  # tolera {"itens": [...]}
        dados = next((v for v in dados.values() if isinstance(v, list)), None)
    if not isinstance(dados, list):
        log.warning("resposta da IA não é uma lista")
        return []

    resultados: dict[int, Resultado] = {}
    for bruto in dados:
        try:
            resultado = Resultado.model_validate(bruto)
        except ValidationError as erro:
            id_bruto = bruto.get("id") if isinstance(bruto, dict) else None
            log.warning("item %s inválido na resposta da IA: %s", id_bruto, erro.errors()[0]["msg"])
            continue
        if resultado.id not in ids_esperados or resultado.id in resultados:
            log.warning("id %s inesperado ou repetido na resposta da IA", resultado.id)
            continue
        if tags_validas is not None:
            resultado.tags = [t for t in resultado.tags if t in tags_validas] or ["outros"]
        resultados[resultado.id] = resultado
    return list(resultados.values())


# ----------------------------------------------------------------- chamada


@lru_cache(maxsize=1)
def _cliente_genai() -> genai.Client:
    chave = config.carregar().exigir_gemini()
    return genai.Client(
        api_key=chave,
        http_options=types.HttpOptions(
            timeout=TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),  # retentativas ficam por nossa conta
        ),
    )


def _chamar_modelo(instrucoes: str, conteudo: str, esquema: dict[str, Any]) -> str:
    resposta = _cliente_genai().models.generate_content(
        model=config.carregar().gemini_model,
        contents=conteudo,
        config=types.GenerateContentConfig(
            system_instruction=instrucoes,
            response_mime_type="application/json",
            response_json_schema=esquema,
            temperature=0.2,
        ),
    )
    return resposta.text or ""


def com_retentativas[T](chamar: Callable[[], T], dormir: Callable[[float], None] = time.sleep) -> T:
    """Backoff exponencial (5s, 15s, 45s) em 429, 5xx e falhas de rede."""
    for tentativa in range(MAX_RETENTATIVAS + 1):
        try:
            return chamar()
        except errors.APIError as erro:
            codigo = erro.code or 0
            if codigo != 429 and codigo < 500:
                raise ErroIA(f"Gemini respondeu {codigo}: {erro.message}") from erro
            if tentativa == MAX_RETENTATIVAS:
                if codigo == 429:
                    raise CotaEsgotada(f"cota do Gemini esgotada: {erro.message}") from erro
                raise ErroIA(f"Gemini indisponível ({codigo}): {erro.message}") from erro
            motivo = f"HTTP {codigo}"
        except httpx.HTTPError as erro:
            if tentativa == MAX_RETENTATIVAS:
                raise ErroIA(f"falha de rede ao chamar o Gemini: {erro}") from erro
            motivo = type(erro).__name__
        espera = ESPERA_BASE_SEGUNDOS * 3**tentativa
        log.warning(
            "IA: %s; nova tentativa em %.0fs (%d/%d)",
            motivo,
            espera,
            tentativa + 1,
            MAX_RETENTATIVAS,
        )
        dormir(espera)
    raise AssertionError("inalcançável")  # pragma: no cover


def classificar_lote(itens: Sequence[ItemPendente], modulo: Modulo) -> list[Resultado]:
    """Classifica um lote de itens de um módulo numa única chamada ao modelo.

    Devolve só os resultados válidos; os itens que faltarem devem continuar pendentes.
    """
    if not itens:
        return []
    instrucoes = montar_instrucoes(modulo, config.carregar_perfil(), date.today())
    conteudo = montar_conteudo(itens)
    texto = com_retentativas(lambda: _chamar_modelo(instrucoes, conteudo, esquema_resposta(modulo)))
    return interpretar_resposta(texto, {i.id for i in itens}, TAGS_POR_MODULO.get(modulo))
