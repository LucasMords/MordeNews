"""Triagem: pega itens pendentes, classifica em lotes e grava o resultado."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from radar import banco
from radar.ia import cliente
from radar.modelos import ItemPendente, Modulo, Resultado

log = logging.getLogger(__name__)

TAMANHO_LOTE = 25
MAXIMO_POR_EXECUCAO = 500
PAUSA_ENTRE_LOTES = 4.0  # segundos; mantém a taxa abaixo do limite por minuto do plano gratuito


@dataclass
class ResumoTriagem:
    modulo: Modulo
    lotes: int = 0
    processados: int = 0
    descartados: int = 0
    sem_resposta: int = 0
    para_erro: int = 0
    interrompido_por_cota: bool = False

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
    execução. Cota esgotada encerra a execução sem erro; os pendentes ficam para a próxima."""
    iniciado_em = datetime.now(UTC)
    resumo = ResumoTriagem(modulo)
    itens = banco.pendentes(modulo, maximo)
    log.info("triagem %s: %d itens pendentes", modulo, len(itens))
    try:
        for numero, lote in enumerate(em_lotes(itens, tamanho_lote)):
            if numero:
                dormir(pausa)
            try:
                resultados = cliente.classificar_lote(lote, modulo)
            except cliente.CotaEsgotada as erro:
                log.warning("triagem %s interrompida: %s", modulo, erro)
                resumo.interrompido_por_cota = True
                break
            _gravar_lote(lote, resultados, resumo)
    except Exception as erro:
        _registrar(resumo, iniciado_em, ok=False, erro=f"{type(erro).__name__}: {erro}")
        raise
    _registrar(resumo, iniciado_em, ok=True)
    return resumo


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
    if resumo.interrompido_por_cota and erro is None:
        erro = "interrompida por cota esgotada; pendentes ficam para a próxima execução"
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
