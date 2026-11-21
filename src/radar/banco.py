"""Única camada que fala com o Supabase.

Usa a API REST do Supabase (PostgREST) via httpx, autenticada com a service role key
(que ignora RLS). Nenhum outro módulo deve montar requisições ao banco.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from typing import Any

import httpx

from radar import config
from radar.modelos import Exemplo, Item, ItemPendente, ItemResumo, Modulo, Resultado

log = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 20.0
MAX_TENTATIVAS_IA = 3

_cliente_atual: httpx.Client | None = None


class ErroBanco(RuntimeError):
    """Falha ao conversar com o Supabase."""


def _cabecalhos(chave: str) -> dict[str, str]:
    cabecalhos = {"apikey": chave, "Content-Type": "application/json"}
    # Chaves antigas (service_role) são JWTs e também vão no Authorization.
    # As novas (sb_secret_...) não são JWT e bastam no header apikey.
    if chave.startswith("eyJ"):
        cabecalhos["Authorization"] = f"Bearer {chave}"
    return cabecalhos


def criar_cliente(url: str, chave: str) -> httpx.Client:
    return httpx.Client(
        base_url=f"{url.rstrip('/')}/rest/v1",
        headers=_cabecalhos(chave),
        timeout=TIMEOUT_SEGUNDOS,
    )


def definir_cliente(cliente: httpx.Client | None) -> None:
    """Troca o cliente HTTP usado pelo módulo (testes injetam um cliente com MockTransport)."""
    global _cliente_atual
    _cliente_atual = cliente


def _cliente() -> httpx.Client:
    global _cliente_atual
    if _cliente_atual is None:
        url, chave = config.carregar().exigir_supabase()
        _cliente_atual = criar_cliente(url, chave)
    return _cliente_atual


def _requisitar(
    metodo: str,
    caminho: str,
    *,
    params: dict[str, str] | None = None,
    json: Any = None,
    prefer: str | None = None,
) -> Any:
    cabecalhos = {"Prefer": prefer} if prefer else None
    try:
        resposta = _cliente().request(metodo, caminho, params=params, json=json, headers=cabecalhos)
    except httpx.HTTPError as erro:
        raise ErroBanco(
            f"Falha de rede ao acessar o Supabase ({metodo} {caminho}): {erro}"
        ) from erro
    if resposta.is_error:
        raise ErroBanco(
            f"Supabase respondeu {resposta.status_code} em {metodo} {caminho}: {_detalhe(resposta)}"
        )
    if not resposta.content:
        return None
    return resposta.json()


def _detalhe(resposta: httpx.Response) -> str:
    try:
        corpo = resposta.json()
    except ValueError:
        return resposta.text[:300]
    if isinstance(corpo, dict):
        partes = [str(corpo[c]) for c in ("message", "details", "hint") if corpo.get(c)]
        return " | ".join(partes) or str(corpo)[:300]
    return str(corpo)[:300]


def _agora() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------- itens


def existe(id_unico: str) -> bool:
    linhas = _requisitar(
        "GET", "/itens", params={"select": "id", "id_unico": f"eq.{id_unico}", "limit": "1"}
    )
    return bool(linhas)


def salvar_itens(itens: Iterable[Item]) -> int:
    """Insere itens ignorando os já existentes (upsert por id_unico). Devolve quantos eram novos."""
    unicos: dict[str, dict[str, Any]] = {}
    for item in itens:
        unicos.setdefault(item.id_unico, item.para_banco())
    if not unicos:
        return 0
    inseridos = _requisitar(
        "POST",
        "/itens",
        params={"on_conflict": "id_unico", "select": "id_unico"},
        json=list(unicos.values()),
        prefer="resolution=ignore-duplicates,return=representation",
    )
    novos = len(inseridos or [])
    log.info("salvar_itens: %d recebidos, %d novos", len(unicos), novos)
    return novos


def obter_item(id_unico: str) -> dict[str, Any] | None:
    linhas = _requisitar(
        "GET", "/itens", params={"select": "*", "id_unico": f"eq.{id_unico}", "limit": "1"}
    )
    return linhas[0] if linhas else None


def apagar_item(id_unico: str) -> None:
    """Apaga um item pelo id_unico. Uso restrito a dados de teste (ex.: `radar teste-banco`)."""
    _requisitar("DELETE", "/itens", params={"id_unico": f"eq.{id_unico}"})


def pendentes(modulo: Modulo, limite: int) -> list[ItemPendente]:
    """Itens aguardando triagem, dos mais recentes para os mais antigos.

    Os mais novos vêm primeiro para que, se a cota da IA acabar, o resumo do dia já esteja triado.
    """
    linhas = _requisitar(
        "GET",
        "/itens",
        params={
            "select": "id,modulo,fonte,titulo,url,texto,tentativas_ia",
            "status": "eq.pendente",
            "modulo": f"eq.{modulo}",
            "order": "coletado_em.desc,id.desc",
            "limit": str(limite),
        },
    )
    return [ItemPendente.model_validate(linha) for linha in linhas or []]


def gravar_triagem(resultados: Sequence[Resultado]) -> None:
    """Grava nota, resumo, tags, campos e prazo, e muda o status para processado/descartado."""
    for r in resultados:
        _requisitar(
            "PATCH",
            "/itens",
            params={"id": f"eq.{r.id}", "status": "eq.pendente"},
            json={
                "nota": r.nota,
                "resumo": r.resumo,
                "tags": r.tags,
                "campos": r.campos,
                "prazo": r.prazo.isoformat() if r.prazo else None,
                "status": r.status,
            },
            prefer="return=minimal",
        )


def registrar_falha_ia(itens: Sequence[ItemPendente], maximo: int = MAX_TENTATIVAS_IA) -> int:
    """Incrementa tentativas_ia; no máximo de tentativas o item vai para 'erro'.

    Devolve quantos itens foram para 'erro'.
    """
    para_erro = 0
    for item in itens:
        tentativas = item.tentativas_ia + 1
        status = "erro" if tentativas >= maximo else "pendente"
        para_erro += status == "erro"
        _requisitar(
            "PATCH",
            "/itens",
            params={"id": f"eq.{item.id}"},
            json={"tentativas_ia": tentativas, "status": status},
            prefer="return=minimal",
        )
    return para_erro


def triados_recentes(modulo: Modulo, limite: int) -> list[dict[str, Any]]:
    """Últimos itens triados (processados ou descartados), para revisão humana."""
    linhas = _requisitar(
        "GET",
        "/itens",
        params={
            "select": "id,fonte,titulo,url,nota,resumo,tags,status,prazo,campos",
            "modulo": f"eq.{modulo}",
            "status": "in.(processado,descartado)",
            "order": "coletado_em.desc,id.desc",
            "limit": str(limite),
        },
    )
    return list(linhas or [])


def para_resumo(
    desde: datetime,
    nota_minima: int,
    limite: int = 500,
    modulos: Sequence[str] | None = None,
) -> list[ItemResumo]:
    """Itens processados, ainda não enviados, coletados a partir de `desde` e com nota mínima.

    `modulos` restringe a busca (padrão: todos). Vêm ordenados por nota (maior primeiro) e, no
    empate, pelos mais recentes.
    """
    params = {
        "select": "id,modulo,fonte,titulo,url,publicado_em,nota,resumo,tags,prazo,campos",
        "status": "eq.processado",
        "enviado_em": "is.null",
        "nota": f"gte.{nota_minima}",
        "coletado_em": f"gte.{desde.isoformat()}",
        "order": "nota.desc,publicado_em.desc.nullslast,id.desc",
        "limit": str(limite),
    }
    if modulos:
        params["modulo"] = f"in.({','.join(modulos)})"
    linhas = _requisitar("GET", "/itens", params=params)
    return [ItemResumo.model_validate(linha) for linha in linhas or []]


def com_prazo(inicio: date, fim: date, limite: int = 500) -> list[ItemResumo]:
    """Itens processados (enviados ou não) com prazo entre `inicio` e `fim`, do mais próximo."""
    linhas = _requisitar(
        "GET",
        "/itens",
        params={
            "select": "id,modulo,fonte,titulo,url,publicado_em,nota,resumo,tags,prazo,campos,salvo",
            "status": "eq.processado",
            "prazo": f"gte.{inicio.isoformat()}",
            "order": "prazo.asc,id.asc",
            "limit": str(limite),
        },
    )
    itens = [ItemResumo.model_validate(linha) for linha in linhas or []]
    return [i for i in itens if i.prazo is not None and i.prazo <= fim]


def _filtro_limpeza(antes: datetime) -> dict[str, str]:
    """Itens já triados, não salvos, coletados antes de `antes` e que ainda têm texto."""
    return {
        "coletado_em": f"lt.{antes.astimezone(UTC).isoformat()}",
        "salvo": "eq.false",
        "status": "neq.pendente",
        "texto": "not.is.null",
    }


def contar_para_limpeza(antes: datetime) -> int:
    linhas = _requisitar("GET", "/itens", params={"select": "id", **_filtro_limpeza(antes)})
    return len(linhas or [])


def limpar_textos(antes: datetime) -> int:
    """Apaga o `texto` (só ele) dos itens antigos não salvos. Devolve quantos foram limpos.

    Título, resumo, nota, link e campos continuam no banco.
    """
    limpos = _requisitar(
        "PATCH",
        "/itens",
        params={"select": "id", **_filtro_limpeza(antes)},
        json={"texto": None},
        prefer="return=representation",
    )
    return len(limpos or [])


def marcar_enviados(ids: Sequence[int]) -> None:
    if not ids:
        return
    lista = ",".join(str(int(i)) for i in ids)
    _requisitar(
        "PATCH",
        "/itens",
        params={"id": f"in.({lista})"},
        json={"enviado_em": _agora()},
        prefer="return=minimal",
    )


# ------------------------------------------------------------ execucoes


def registrar_execucao(
    coletor: str,
    iniciado_em: datetime,
    ok: bool,
    itens_novos: int = 0,
    erro: str | None = None,
    finalizado_em: datetime | None = None,
) -> None:
    """Grava uma linha em `execucoes` ao fim de uma execução de coletor/comando."""
    _requisitar(
        "POST",
        "/execucoes",
        json={
            "coletor": coletor,
            "iniciado_em": iniciado_em.isoformat(),
            "finalizado_em": (finalizado_em or datetime.now(UTC)).isoformat(),
            "ok": ok,
            "itens_novos": itens_novos,
            "erro": erro[:2000] if erro else None,
        },
        prefer="return=minimal",
    )


def houve_execucao_ok(coletor: str, desde: datetime) -> bool:
    """Se `coletor` teve alguma execução bem-sucedida iniciada a partir de `desde`."""
    linhas = _requisitar(
        "GET",
        "/execucoes",
        params={
            "select": "ok",
            "coletor": f"eq.{coletor}",
            "iniciado_em": f"gte.{desde.astimezone(UTC).isoformat()}",
        },
    )
    return any(linha.get("ok") is True for linha in linhas or [])


def execucoes_desde(
    desde: datetime, coletores: Sequence[str], limite: int = 1000
) -> list[dict[str, Any]]:
    """Execuções dos `coletores` iniciadas a partir de `desde`, das mais novas para as antigas."""
    if not coletores:
        return []
    nomes = ",".join(f'"{nome}"' for nome in coletores)
    linhas = _requisitar(
        "GET",
        "/execucoes",
        params={
            "select": "coletor,iniciado_em,ok,itens_novos,erro",
            "coletor": f"in.({nomes})",
            "iniciado_em": f"gte.{desde.astimezone(UTC).isoformat()}",
            "order": "iniciado_em.desc",
            "limit": str(limite),
        },
    )
    return list(linhas or [])


def ultimas_execucoes(coletor: str, limite: int = 5) -> list[dict[str, Any]]:
    linhas = _requisitar(
        "GET",
        "/execucoes",
        params={
            "select": "*",
            "coletor": f"eq.{coletor}",
            "order": "iniciado_em.desc",
            "limit": str(limite),
        },
    )
    return list(linhas or [])


# ------------------------------------------------------------------ feedback (bloco 7)


def exemplos_feedback(modulo: Modulo, desde: datetime, limite: int = 10) -> list[Exemplo]:
    """Votos 👍/👎 do portal desde `desde`, com o título do item, para calibrar a triagem.

    Devolve até `limite` de cada tipo (👍 primeiro), dos votos mais recentes para os antigos.
    """
    votos = _requisitar(
        "GET",
        "/feedback",
        params={
            "select": "item_id,voto,criado_em",
            "criado_em": f"gte.{desde.isoformat()}",
            "order": "criado_em.desc",
            "limit": "300",
        },
    )
    if not votos:
        return []
    ids = ",".join(str(v["item_id"]) for v in votos)
    itens = _requisitar(
        "GET",
        "/itens",
        params={"select": "id,titulo,nota", "modulo": f"eq.{modulo}", "id": f"in.({ids})"},
    )
    por_id = {i["id"]: i for i in itens or []}
    gostou: list[Exemplo] = []
    nao_gostou: list[Exemplo] = []
    for voto in votos:
        item = por_id.get(voto["item_id"])
        destino = gostou if voto["voto"] == 1 else nao_gostou
        if item is not None and len(destino) < limite:
            destino.append(Exemplo(titulo=item["titulo"], voto=voto["voto"], nota=item.get("nota")))
    return gostou + nao_gostou
