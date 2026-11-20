"""Ponto de entrada da linha de comando: `radar <comando>`."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from radar import banco, config
from radar.coletores.base import executar
from radar.coletores.http import ClienteHttp
from radar.coletores.registro import filtrar_fontes, montar_coletores
from radar.entrega import alertas, correio, resumo
from radar.ia import cliente as ia_cliente
from radar.ia import triagem
from radar.modelos import Item

log = logging.getLogger("radar")

URL_TESTE = "https://radar.invalid/teste-banco?utm_source=radar"


class FalhaVerificacao(Exception):
    """Uma checagem do teste-banco não deu o resultado esperado."""


def _configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # httpx e o SDK do Gemini logam cada requisição em INFO; deixamos só avisos para não poluir.
    for ruidoso in ("httpx", "httpx2", "google_genai"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def _verificar(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise FalhaVerificacao(mensagem)
    log.info("ok: %s", mensagem)


def comando_teste_banco(args: argparse.Namespace) -> int:
    """Grava, relê e (por padrão) apaga um item de teste no Supabase."""
    iniciado_em = datetime.now(UTC)
    item = Item(
        modulo="noticias",
        fonte="teste-banco",
        titulo="Item de teste do radar",
        url=URL_TESTE,
        publicado_em=iniciado_em,
        texto="Gerado por `radar teste-banco` para validar a conexão com o Supabase.",
    )

    if banco.existe(item.id_unico):
        log.info("item de teste de uma execução anterior encontrado; removendo antes de testar")
        banco.apagar_item(item.id_unico)

    _verificar(banco.salvar_itens([item]) == 1, "primeira gravação inseriu 1 item novo")
    _verificar(banco.salvar_itens([item]) == 0, "segunda gravação não duplicou o item")
    _verificar(banco.existe(item.id_unico), "existe() encontra o item pelo id_unico")

    gravado = banco.obter_item(item.id_unico)
    _verificar(gravado is not None and gravado["titulo"] == item.titulo, "item relido do banco")
    _verificar(
        gravado is not None and gravado["status"] == "pendente", "status inicial é 'pendente'"
    )
    log.info("item gravado: id_unico=%s…", item.id_unico[:12])

    banco.registrar_execucao("teste-banco", iniciado_em=iniciado_em, ok=True, itens_novos=1)
    execucoes = banco.ultimas_execucoes("teste-banco", limite=1)
    _verificar(bool(execucoes) and execucoes[0]["ok"] is True, "execução registrada em execucoes")

    if args.manter:
        log.info("item de teste mantido no banco (--manter)")
    else:
        banco.apagar_item(item.id_unico)
        _verificar(not banco.existe(item.id_unico), "item de teste removido")

    log.info("teste-banco concluído com sucesso")
    return 0


def comando_coletar(args: argparse.Namespace) -> int:
    """Roda os coletores escolhidos. Falha (código 1) só se nenhum coletor der certo."""
    cfg = config.carregar()
    cfg.exigir_supabase()  # falha logo se o banco não estiver configurado
    fontes = filtrar_fontes(
        config.carregar_fontes_validas(), nomes=args.fonte or (), modulo=args.modulo
    )
    if not fontes:
        log.error("nenhuma fonte corresponde aos filtros informados")
        return 1

    with ClienteHttp(cfg.user_agent) as http:
        resultados = [executar(c) for c in montar_coletores(fontes, http)]

    falhas = [r for r in resultados if not r.ok]
    novos = sum(r.novos for r in resultados)
    log.info(
        "coleta concluída: %d fontes, %d ok, %d com falha, %d itens novos",
        len(resultados),
        len(resultados) - len(falhas),
        len(falhas),
        novos,
    )
    for falha in falhas:
        log.warning("falhou: %s — %s", falha.coletor, falha.erro)
    return 1 if len(falhas) == len(resultados) else 0


def comando_triar(args: argparse.Namespace) -> int:
    """Tria os pendentes. Cota esgotada ou modelo sobrecarregado não é falha; outro erro da IA
    ou do banco é."""
    cfg = config.carregar()
    cfg.exigir_supabase()
    cfg.exigir_gemini()
    config.carregar_perfil()  # falha logo se o perfil não existir
    modulos = [args.modulo] if args.modulo else ia_cliente.modulos_com_prompt()
    for modulo in modulos:
        resumo = triagem.triar(modulo, tamanho_lote=args.lote, maximo=args.max)
        log.info(
            "triagem %s concluída: %d processados, %d descartados, %d sem resposta "
            "(%d foram para 'erro')%s",
            modulo,
            resumo.processados,
            resumo.descartados,
            resumo.sem_resposta,
            resumo.para_erro,
            f" — interrompida ({resumo.interrompido})" if resumo.interrompido else "",
        )
        if resumo.interrompido:
            break
    return 0


def comando_revisar(args: argparse.Namespace) -> int:
    """Mostra os últimos itens triados para conferir se as notas fazem sentido."""
    itens = banco.triados_recentes(args.modulo, args.quantidade)
    if not itens:
        log.info("nenhum item triado em %s ainda", args.modulo)
        return 0
    itens.sort(key=lambda i: i["nota"] or 0, reverse=True)
    for item in itens:
        marca = " [descartado]" if item["status"] == "descartado" else ""
        print(f"\n[{item['nota']:>2}] {item['titulo']}{marca}")
        print(f"     {item['fonte']} · {', '.join(item['tags'] or [])} · id {item['id']}")
        print(f"     {item['resumo']}")
        campos = {k: v for k, v in (item.get("campos") or {}).items() if v not in (None, [], "")}
        if campos:
            print(f"     campos: {campos}")
        if item.get("prazo"):
            print(f"     prazo: {item['prazo']}")
        print(f"     {item['url']}")
    return 0


def comando_resumo(args: argparse.Namespace) -> int:
    """Envia o resumo diário por e-mail (ou só mostra, com --simular)."""
    config.carregar().exigir_supabase()
    resultado = resumo.enviar_resumo(simular=args.simular, reserva=args.reserva)
    if args.simular and resultado.mensagem:
        print(f"Assunto: {resultado.mensagem.assunto}\n")
        print(resultado.mensagem.texto)
        if args.salvar:
            args.salvar.write_text(resultado.mensagem.html, encoding="utf-8")
            log.info("prévia HTML salva em %s", args.salvar)
    return 0


def comando_alertas_prazo(args: argparse.Namespace) -> int:
    """Avisa por e-mail as inscrições que terminam em até 3 dias (ou só mostra, com --simular)."""
    config.carregar().exigir_supabase()
    resultado = alertas.enviar_alertas(simular=args.simular)
    if args.simular:
        if resultado.mensagem:
            print(f"Assunto: {resultado.mensagem.assunto}\n")
            print(resultado.mensagem.texto)
        else:
            print("Nenhum prazo terminando nos próximos 3 dias.")
    return 0


def _montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="radar", description="Radar pessoal de informação.")
    sub = parser.add_subparsers(dest="comando", required=True)

    coletar = sub.add_parser("coletar", help="busca itens novos nas fontes do fontes.yaml")
    escolha = coletar.add_mutually_exclusive_group(required=True)
    escolha.add_argument("--todos", action="store_true", help="todas as fontes")
    escolha.add_argument(
        "--fonte", action="append", metavar="NOME", help="só esta fonte (pode repetir)"
    )
    escolha.add_argument("--modulo", choices=["noticias", "estagios", "concursos"])
    coletar.set_defaults(funcao=comando_coletar)

    triar = sub.add_parser("triar", help="classifica os itens pendentes com a IA")
    triar.add_argument("--modulo", choices=["noticias", "estagios", "concursos"])
    triar.add_argument(
        "--max",
        type=int,
        default=triagem.MAXIMO_POR_EXECUCAO,
        help="máximo de itens nesta execução",
    )
    triar.add_argument(
        "--lote", type=int, default=triagem.TAMANHO_LOTE, help="itens por chamada à IA (20 a 30)"
    )
    triar.set_defaults(funcao=comando_triar)

    revisar = sub.add_parser("revisar", help="lista os últimos itens triados, por nota")
    revisar.add_argument(
        "--modulo", choices=["noticias", "estagios", "concursos"], default="noticias"
    )
    revisar.add_argument("--quantidade", type=int, default=20)
    revisar.set_defaults(funcao=comando_revisar)

    resumo_cmd = sub.add_parser("resumo", help="envia o resumo diário por e-mail")
    resumo_cmd.add_argument(
        "--simular", action="store_true", help="monta e mostra o resumo, sem enviar nem marcar"
    )
    resumo_cmd.add_argument(
        "--salvar", type=Path, metavar="ARQUIVO.html", help="com --simular, salva a prévia HTML"
    )
    resumo_cmd.add_argument(
        "--reserva",
        action="store_true",
        help="execução de reserva: só envia se o resumo de hoje ainda não deu certo",
    )
    resumo_cmd.set_defaults(funcao=comando_resumo)

    alerta_cmd = sub.add_parser(
        "alertas-prazo", help="avisa por e-mail as inscrições que terminam em até 3 dias"
    )
    alerta_cmd.add_argument("--simular", action="store_true", help="mostra o alerta, sem enviar")
    alerta_cmd.set_defaults(funcao=comando_alertas_prazo)

    teste = sub.add_parser("teste-banco", help="grava e lê um item de teste no Supabase")
    teste.add_argument("--manter", action="store_true", help="não apaga o item de teste ao final")
    teste.set_defaults(funcao=comando_teste_banco)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configurar_logs()
    args = _montar_parser().parse_args(argv)
    funcao: Callable[[argparse.Namespace], int] = args.funcao
    try:
        return funcao(args)
    except config.ErroConfiguracao as erro:
        log.error("configuração: %s", erro)
    except banco.ErroBanco as erro:
        log.error("banco: %s", erro)
    except ia_cliente.ErroIA as erro:
        log.error("IA: %s", erro)
    except correio.ErroEnvio as erro:
        log.error("e-mail: %s", erro)
    except FalhaVerificacao as erro:
        log.error("verificação falhou: %s", erro)
    return 1


if __name__ == "__main__":
    sys.exit(main())
