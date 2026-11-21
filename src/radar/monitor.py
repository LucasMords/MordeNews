"""Monitoramento (bloco 9): alerta de coletores com problema e limpeza mensal do banco.

Um coletor tem problema quando:
- **falha:** as 2 últimas execuções falharam;
- **sem itens:** passou 3 dias sem nenhum item novo, mesmo rodando bem. Só vale para fontes
  monitoradas há mais de 3 dias, para uma fonte recém-adicionada não disparar o alerta.

Cada problema é avisado uma vez, e de novo só se continuar depois de `REPETIR_APOS_DIAS`.
Os problemas avisados ficam no campo `erro` da execução `monitor` em `execucoes`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from radar import banco, config
from radar.entrega import correio

log = logging.getLogger(__name__)

COLETOR = "monitor"
COLETOR_LIMPEZA = "limpeza"
FALHAS_SEGUIDAS = 2
DIAS_SEM_ITENS = 3
REPETIR_APOS_DIAS = 7
DIAS_GUARDAR_TEXTO = 90

TipoProblema = Literal["falha", "sem-itens"]


@dataclass(frozen=True)
class Problema:
    fonte: str
    tipo: TipoProblema
    detalhe: str

    @property
    def chave(self) -> str:
        return f"{self.tipo}:{self.fonte}"


@dataclass(frozen=True)
class ResultadoMonitor:
    problemas: list[Problema]  # todos os detectados agora
    novos: list[Problema]  # os que entram no e-mail
    mensagem: correio.Mensagem | None


def _data(valor: str) -> datetime:
    return datetime.fromisoformat(valor)


def diagnosticar(
    execucoes: Sequence[dict[str, Any]], fontes: Sequence[str], agora: datetime
) -> list[Problema]:
    """Problemas de cada fonte a partir das execuções recentes (de qualquer ordem)."""
    corte = agora - timedelta(days=DIAS_SEM_ITENS)
    problemas: list[Problema] = []
    for fonte in fontes:
        da_fonte = sorted(
            (e for e in execucoes if e["coletor"] == fonte),
            key=lambda e: _data(e["iniciado_em"]),
            reverse=True,
        )
        ultimas = da_fonte[:FALHAS_SEGUIDAS]
        if len(ultimas) == FALHAS_SEGUIDAS and not any(e["ok"] for e in ultimas):
            erro = ultimas[0].get("erro") or "sem mensagem de erro"
            detalhe = f"{FALHAS_SEGUIDAS} falhas seguidas. Último erro: {erro}"
            problemas.append(Problema(fonte, "falha", detalhe))
            continue

        recentes = [e for e in da_fonte if _data(e["iniciado_em"]) >= corte]
        monitorada_ha_tempo = any(_data(e["iniciado_em"]) < corte for e in da_fonte)
        rodou_bem = any(e["ok"] for e in recentes)
        sem_novos = sum(e.get("itens_novos") or 0 for e in recentes) == 0
        if monitorada_ha_tempo and rodou_bem and sem_novos:
            detalhe = f"{DIAS_SEM_ITENS} dias sem itens novos, mesmo rodando sem erro"
            problemas.append(Problema(fonte, "sem-itens", detalhe))
    return problemas


def _ja_avisados(agora: datetime) -> tuple[set[str], bool]:
    """Chaves avisadas nos últimos dias e se o monitor já rodou hoje (dia de Brasília)."""
    desde = agora - timedelta(days=REPETIR_APOS_DIAS)
    meia_noite = agora.astimezone(correio.BRASILIA).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    avisados: set[str] = set()
    rodou_hoje = False
    for execucao in banco.execucoes_desde(desde, [COLETOR]):
        if not execucao["ok"]:
            continue
        avisados.update((execucao.get("erro") or "").split())
        rodou_hoje = rodou_hoje or _data(execucao["iniciado_em"]) >= meia_noite
    return avisados, rodou_hoje


def monitorar(*, simular: bool = False, agora: datetime | None = None) -> ResultadoMonitor:
    """Verifica os coletores do fontes.yaml e avisa por e-mail os problemas novos.

    No máximo uma verificação por dia (o resumo-diario roda duas vezes). Em `simular`, mostra
    todos os problemas atuais, sem enviar nem registrar.
    """
    cfg = config.carregar()
    credenciais = None if simular else cfg.exigir_email()
    agora = agora or datetime.now(UTC)
    iniciado_em = datetime.now(UTC)

    avisados: set[str] = set()
    if credenciais is not None:
        avisados, rodou_hoje = _ja_avisados(agora)
        if rodou_hoje:
            log.info("monitor: a verificação de hoje já foi feita; nada a fazer")
            return ResultadoMonitor([], [], None)

    fontes = [f.nome for f in config.carregar_fontes_validas()]
    # Folga de 1 dia na janela, para saber se a fonte já era monitorada antes dos 3 dias.
    execucoes = banco.execucoes_desde(agora - timedelta(days=DIAS_SEM_ITENS + 1), fontes)
    problemas = diagnosticar(execucoes, fontes, agora)
    novos = [p for p in problemas if p.chave not in avisados]
    log.info(
        "monitor: %d fontes verificadas, %d com problema, %d a avisar",
        len(fontes),
        len(problemas),
        len(novos),
    )
    for problema in problemas:
        log.warning("monitor: %s — %s", problema.fonte, problema.detalhe)

    hoje = agora.astimezone(correio.BRASILIA).date()
    mensagem = correio.montar_monitor(novos, hoje) if novos else None
    if credenciais is None:
        return ResultadoMonitor(problemas, novos, mensagem)

    if mensagem is not None:
        remetente, senha, destino = credenciais
        correio.enviar(
            mensagem,
            remetente=remetente,
            senha_app=senha,
            destino=destino,
            host=cfg.smtp_host,
            porta=cfg.smtp_porta,
        )
    # Grava só os avisados agora: quem continuar com problema volta a ser avisado em 7 dias.
    chaves = " ".join(sorted(p.chave for p in novos))
    _registrar(COLETOR, iniciado_em, ok=True, quantidade=len(novos), nota=chaves)
    return ResultadoMonitor(problemas, novos, mensagem)


def limpar(*, simular: bool = False, agora: datetime | None = None) -> int:
    """Apaga o `texto` dos itens com mais de 90 dias que não foram salvos.

    O Supabase gratuito tem 500 MB; o texto bruto é o que mais ocupa. Devolve quantos itens
    foram (ou, em `simular`, seriam) limpos.
    """
    agora = agora or datetime.now(UTC)
    iniciado_em = datetime.now(UTC)
    antes = agora - timedelta(days=DIAS_GUARDAR_TEXTO)
    if simular:
        quantidade = banco.contar_para_limpeza(antes)
        log.info("limpeza (simulação): %d itens teriam o texto apagado", quantidade)
        return quantidade
    quantidade = banco.limpar_textos(antes)
    log.info("limpeza: texto apagado de %d itens coletados antes de %s", quantidade, antes.date())
    _registrar(COLETOR_LIMPEZA, iniciado_em, ok=True, quantidade=quantidade)
    return quantidade


def _registrar(
    coletor: str, iniciado_em: datetime, *, ok: bool, quantidade: int, nota: str | None = None
) -> None:
    try:
        banco.registrar_execucao(
            coletor, iniciado_em=iniciado_em, ok=ok, itens_novos=quantidade, erro=nota or None
        )
    except banco.ErroBanco as falha:
        log.error("%s: não foi possível registrar a execução — %s", coletor, falha)
