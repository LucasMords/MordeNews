"""Alerta de prazo: avisa por e-mail as inscrições que terminam em até 3 dias.

Entram os concursos (todos, porque não são filtrados por nota), as vagas e notícias com nota
de destaque no resumo e qualquer item salvo pelo usuário. No máximo um alerta por dia: o
comando confere em `execucoes` se o alerta de hoje já deu certo.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from radar import banco, config
from radar.entrega import correio
from radar.modelos import ItemResumo

log = logging.getLogger(__name__)

COLETOR = "alertas-prazo"
DIAS_ANTES = 3


@dataclass(frozen=True)
class ResultadoAlerta:
    itens: int
    mensagem: correio.Mensagem | None


def deve_alertar(item: ItemResumo, nota_minima: int) -> bool:
    return item.salvo or item.modulo == "concursos" or item.nota >= nota_minima


def selecionar(itens: Sequence[ItemResumo], nota_minima: int) -> list[ItemResumo]:
    return [i for i in itens if deve_alertar(i, nota_minima)]


def enviar_alertas(*, simular: bool = False, agora: datetime | None = None) -> ResultadoAlerta:
    """Envia o alerta do dia, se houver prazos. Em `simular`, só monta a mensagem."""
    cfg = config.carregar()
    credenciais = None if simular else cfg.exigir_email()  # falha logo se faltar configuração
    agora = agora or datetime.now(UTC)
    iniciado_em = datetime.now(UTC)
    hoje = agora.astimezone(correio.BRASILIA).date()
    if credenciais is not None and _ja_alertado(hoje):
        log.info("alertas-prazo: o alerta de hoje já foi enviado; nada a fazer")
        return ResultadoAlerta(0, None)

    candidatos = banco.com_prazo(hoje, hoje + timedelta(days=DIAS_ANTES))
    itens = selecionar(candidatos, cfg.nota_minima_resumo)
    log.info(
        "alertas-prazo: %d itens com prazo até 3 dias, %d no alerta", len(candidatos), len(itens)
    )
    if not itens:
        if credenciais is not None:
            _registrar(iniciado_em, ok=True, enviados=0)
        return ResultadoAlerta(0, None)

    mensagem = correio.montar_alerta(itens, hoje)
    if credenciais is None:
        log.info("alertas-prazo (simulação): nada enviado")
        return ResultadoAlerta(len(itens), mensagem)

    remetente, senha, destino = credenciais
    try:
        correio.enviar(
            mensagem,
            remetente=remetente,
            senha_app=senha,
            destino=destino,
            host=cfg.smtp_host,
            porta=cfg.smtp_porta,
        )
    except correio.ErroEnvio as erro:
        _registrar(iniciado_em, ok=False, enviados=0, erro=str(erro))
        raise
    _registrar(iniciado_em, ok=True, enviados=len(itens))
    return ResultadoAlerta(len(itens), mensagem)


def _ja_alertado(hoje: date) -> bool:
    meia_noite = datetime(hoje.year, hoje.month, hoje.day, tzinfo=correio.BRASILIA)
    return banco.houve_execucao_ok(COLETOR, desde=meia_noite)


def _registrar(iniciado_em: datetime, *, ok: bool, enviados: int, erro: str | None = None) -> None:
    try:
        banco.registrar_execucao(
            COLETOR, iniciado_em=iniciado_em, ok=ok, itens_novos=enviados, erro=erro
        )
    except banco.ErroBanco as falha:
        log.error("alertas-prazo: não foi possível registrar a execução — %s", falha)
