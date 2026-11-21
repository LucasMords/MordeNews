"""Resumo diário: agrupa repetidos, seleciona, envia o e-mail e marca como enviados."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from radar import banco, config
from radar.entrega import correio
from radar.entrega.agrupamento import agrupar
from radar.entrega.correio import Assunto
from radar.modelos import ItemResumo

log = logging.getLogger(__name__)

JANELA_HORAS = 36  # cobre o intervalo entre coletas com folga para cron atrasado
_SEM_PRAZO = date.max


@dataclass(frozen=True)
class ResultadoResumo:
    assuntos: int  # entradas no e-mail
    enviados: int  # itens marcados como enviados (inclui os repetidos agrupados)
    fora: int  # itens com nota suficiente que não couberam no limite
    mensagem: correio.Mensagem | None


def selecionar(
    itens: Sequence[ItemResumo], maximo: int, *, por_prazo: bool = False
) -> tuple[list[Assunto], list[Assunto]]:
    """Agrupa repetidos e devolve os `maximo` primeiros assuntos e os que ficaram de fora.

    A ordem é por nota; com `por_prazo` (concursos), pelo prazo mais próximo, sem prazo no fim.
    """
    assuntos = agrupar(itens)
    if por_prazo:
        assuntos.sort(key=lambda a: a.principal.prazo or _SEM_PRAZO)
    return assuntos[:maximo], assuntos[maximo:]


def _encerrado(item: ItemResumo, agora: datetime) -> bool:
    """Inscrição já terminou (ex.: retificação de um concurso antigo listada no PCI)."""
    hoje = agora.astimezone(correio.BRASILIA).date()
    return item.prazo is not None and item.prazo < hoje


def _secoes(cfg: config.Configuracao) -> list[tuple[str, int, int]]:
    """(módulo, nota mínima, máximo de assuntos). Cada módulo tem limite próprio, para vagas e
    concursos não disputarem espaço com as notícias. Vagas e concursos aparecem mesmo com nota
    baixa (pedidos do usuário em 2026-11-20)."""
    return [
        ("noticias", cfg.nota_minima_resumo, cfg.resumo_maximo),
        ("estagios", cfg.nota_minima_estagios, cfg.estagios_maximo),
        ("concursos", cfg.nota_minima_concursos, cfg.concursos_maximo),
    ]


def ja_enviado_hoje(agora: datetime) -> bool:
    """Se já houve um resumo bem-sucedido hoje (dia de Brasília), com ou sem e-mail."""
    meia_noite = agora.astimezone(correio.BRASILIA).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return banco.houve_execucao_ok("resumo-diario", desde=meia_noite)


def enviar_resumo(
    *, simular: bool = False, agora: datetime | None = None, reserva: bool = False
) -> ResultadoResumo:
    """Envia o resumo do dia. Sem itens, não envia nada. Em `simular`, só monta a mensagem.

    Em `reserva` (execução das 15h), só age se o resumo da manhã não deu certo ou não rodou.
    """
    cfg = config.carregar()
    credenciais = None if simular else cfg.exigir_email()  # falha logo se faltar configuração
    agora = agora or datetime.now(UTC)
    iniciado_em = datetime.now(UTC)
    if reserva and ja_enviado_hoje(agora):
        log.info("resumo (reserva): o resumo de hoje já deu certo; nada a fazer")
        return ResultadoResumo(0, 0, 0, None)

    desde = agora - timedelta(hours=JANELA_HORAS)
    candidatos: list[ItemResumo] = []
    escolhidos: list[Assunto] = []
    de_fora: list[Assunto] = []
    tem_vagas = False
    for modulo, nota_minima, maximo in _secoes(cfg):
        itens = banco.para_resumo(desde, nota_minima, modulos=(modulo,))
        if modulo == "concursos":
            itens = [i for i in itens if not _encerrado(i, agora)]
        dentro, fora_modulo = selecionar(itens, maximo, por_prazo=modulo == "concursos")
        candidatos += itens
        escolhidos += dentro
        de_fora += fora_modulo
        tem_vagas = tem_vagas or (modulo == "estagios" and bool(dentro))
    ids = [item.id for assunto in escolhidos for item in assunto.itens]
    fora = sum(len(a.itens) for a in de_fora)
    if not escolhidos:
        log.info("resumo: nenhum item novo para enviar")
        if credenciais is not None:
            _registrar(iniciado_em, ok=True, enviados=0)
        return ResultadoResumo(0, 0, 0, None)

    hoje = agora.astimezone(correio.BRASILIA).date()
    mensagem = correio.montar_mensagem(
        escolhidos,
        hoje,
        nota_minima=cfg.nota_minima_resumo,
        fora=fora,
        nota_minima_estagios=cfg.nota_minima_estagios if tem_vagas else None,
        portal_url=cfg.portal_url,
    )
    resultado = ResultadoResumo(len(escolhidos), len(ids), fora, mensagem)
    log.info(
        "resumo: %d candidatos → %d assuntos no e-mail (%d itens), %d itens de fora",
        len(candidatos),
        resultado.assuntos,
        resultado.enviados,
        fora,
    )
    if credenciais is None:
        log.info("resumo (simulação): nada enviado nem marcado")
        return resultado

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
    banco.marcar_enviados(ids)  # só depois do envio dar certo
    _registrar(iniciado_em, ok=True, enviados=len(ids))
    return resultado


def _registrar(iniciado_em: datetime, *, ok: bool, enviados: int, erro: str | None = None) -> None:
    try:
        banco.registrar_execucao(
            "resumo-diario", iniciado_em=iniciado_em, ok=ok, itens_novos=enviados, erro=erro
        )
    except banco.ErroBanco as falha:
        log.error("resumo: não foi possível registrar a execução — %s", falha)
