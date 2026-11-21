"""Triagem: pega itens pendentes, classifica em lotes e grava o resultado."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from radar import banco
from radar.ia import cliente
from radar.modelos import Exemplo, ItemPendente, Modulo, Resultado

log = logging.getLogger(__name__)

TAMANHO_LOTE = 25
MAXIMO_POR_EXECUCAO = 500
PAUSA_ENTRE_LOTES = 4.0  # segundos; mantém a taxa abaixo do limite por minuto do plano gratuito
DIAS_EXEMPLOS = 90  # votos do portal mais antigos que isso não entram no prompt
EXEMPLOS_POR_TIPO = 10  # até 10 👍 e 10 👎


@dataclass
class ResumoTriagem:
    modulo: Modulo
    lotes: int = 0
    processados: int = 0
    descartados: int = 0
    sem_resposta: int = 0
    para_erro: int = 0
    interrompido: str | None = None  # motivo, quando a IA ficou temporariamente fora

    @property
    def triados(self) -> int:
        return self.processados + self.descartados


def em_lotes(itens: Sequence[ItemPendente], tamanho: int) -> Iterator[Sequence[ItemPendente]]:
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def triar(
    modulo: Modulo,
    *,
    tamanho_lote: int = TAMANHO_LOTE,
    maximo: int = MAXIMO_POR_EXECUCAO,
    pausa: float = PAUSA_ENTRE_LOTES,
    dormir: Callable[[float], None] = time.sleep,
) -> ResumoTriagem:
    """Tria até `maximo` itens pendentes do módulo. Cada item tem no máximo uma tentativa por
    execução. Cota esgotada ou modelo sobrecarregado (5xx) encerra a execução sem erro; os
    pendentes ficam para a próxima."""
    iniciado_em = datetime.now(UTC)
    resumo = ResumoTriagem(modulo)
    itens = banco.pendentes(modulo, maximo)
    log.info("triagem %s: %d itens pendentes", modulo, len(itens))
    exemplos = carregar_exemplos(modulo, iniciado_em) if itens else []
    try:
        for numero, lote in enumerate(em_lotes(itens, tamanho_lote)):
            if numero:
                dormir(pausa)
            try:
                resultados = cliente.classificar_lote(lote, modulo, exemplos=exemplos)
            except cliente.IATemporariamenteFora as erro:
                log.warning("triagem %s interrompida: %s", modulo, erro)
                resumo.interrompido = (
                    "cota esgotada"
                    if isinstance(erro, cliente.CotaEsgotada)
                    else "modelo indisponível"
                )
                break
            _gravar_lote(lote, resultados, resumo)
    except Exception as erro:
        _registrar(resumo, iniciado_em, ok=False, erro=f"{type(erro).__name__}: {erro}")
        raise
    _registrar(resumo, iniciado_em, ok=True)
    return resumo


def carregar_exemplos(modulo: Modulo, agora: datetime) -> list[Exemplo]:
    """Votos recentes do portal para o prompt. Sem eles a triagem segue normalmente."""
    try:
        exemplos = banco.exemplos_feedback(
            modulo, agora - timedelta(days=DIAS_EXEMPLOS), EXEMPLOS_POR_TIPO
        )
    except banco.ErroBanco as erro:
        log.warning("triagem %s: votos do portal indisponíveis — %s", modulo, erro)
        return []
    if exemplos:
        gostou = sum(e.voto == 1 for e in exemplos)
        log.info(
            "triagem %s: %d votos do portal como exemplo (%d 👍, %d 👎)",
            modulo,
            len(exemplos),
            gostou,
            len(exemplos) - gostou,
        )
    return exemplos


def _gravar_lote(
    lote: Sequence[ItemPendente], resultados: Sequence[Resultado], resumo: ResumoTriagem
) -> None:
    respondidos = {r.id for r in resultados}
    faltantes = [item for item in lote if item.id not in respondidos]
    banco.gravar_triagem(resultados)
    resumo.para_erro += banco.registrar_falha_ia(faltantes)
    resumo.lotes += 1
    resumo.descartados += sum(r.descartar for r in resultados)
    resumo.processados += sum(not r.descartar for r in resultados)
    resumo.sem_resposta += len(faltantes)
    log.info(
        "triagem %s: lote %d com %d itens → %d triados, %d sem resposta válida",
        resumo.modulo,
        resumo.lotes,
        len(lote),
        len(resultados),
        len(faltantes),
    )


def _registrar(
    resumo: ResumoTriagem, iniciado_em: datetime, *, ok: bool, erro: str | None = None
) -> None:
    if resumo.interrompido and erro is None:
        erro = f"interrompida ({resumo.interrompido}); pendentes ficam para a próxima execução"
    try:
        banco.registrar_execucao(
            f"triagem-{resumo.modulo}",
            iniciado_em=iniciado_em,
            ok=ok,
            itens_novos=resumo.triados,
            erro=erro,
        )
    except banco.ErroBanco as falha:
        log.error("triagem %s: não foi possível registrar a execução — %s", resumo.modulo, falha)
