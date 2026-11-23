"""Ferramenta das rotinas do Claude (bloco 8): lê os itens triados e publica a edição.

Roda com qualquer Python 3.11+ e só a biblioteca padrão, para funcionar no ambiente de nuvem
das rotinas sem instalar nada. Não usa a service role key: fala com duas funções do Supabase
(`rotina_itens` e `rotina_publicar`, migração 004) com a chave pública e o ROTINA_TOKEN.

    python scripts/rotina.py gerar-token                 # uma vez, na sua máquina
    python scripts/rotina.py ler --horas 30              # JSON dos itens no stdout
    python scripts/rotina.py publicar diaria edicao.md --titulo "Edição de hoje"

Variáveis: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, ROTINA_TOKEN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

BRASILIA = timezone(timedelta(hours=-3))  # sem horário de verão desde 2019
TIMEOUT = 30
LIMITE_CONTEUDO = 20_000
LIMITE_TITULO = 200
TIPOS = ("diaria", "semanal")


class ErroRotina(Exception):
    """Configuração ausente ou resposta de erro do Supabase."""


def gerar_token() -> tuple[str, str]:
    """Token aleatório (vai para a rotina) e o sha256 dele (vai para o banco)."""
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def ambiente() -> tuple[str, str, str]:
    valores = [os.environ.get(nome, "").strip() for nome in _VARIAVEIS]
    faltando = [nome for nome, valor in zip(_VARIAVEIS, valores, strict=True) if not valor]
    if faltando:
        raise ErroRotina(f"defina as variáveis: {', '.join(faltando)}")
    url, chave, token = valores
    if not url.startswith("https://"):
        raise ErroRotina("SUPABASE_URL precisa começar com https://")
    return url.rstrip("/"), chave, token


_VARIAVEIS = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "ROTINA_TOKEN")


def requisicao_rpc(
    url: str, chave: str, funcao: str, corpo: dict[str, Any]
) -> urllib.request.Request:
    return urllib.request.Request(
        f"{url}/rest/v1/rpc/{funcao}",
        data=json.dumps(corpo).encode(),
        method="POST",
        headers={"apikey": chave, "Content-Type": "application/json", "Accept": "application/json"},
    )


def chamar(funcao: str, corpo: dict[str, Any]) -> Any:
    url, chave, token = ambiente()
    pedido = requisicao_rpc(url, chave, funcao, {"token": token, **corpo})
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
            return json.loads(resposta.read() or b"null")
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode(errors="replace")[:300]
        raise ErroRotina(f"Supabase respondeu {erro.code} em {funcao}: {detalhe}") from None
    except urllib.error.URLError as erro:
        raise ErroRotina(f"sem conexão com o Supabase: {erro.reason}") from None


def compactar(item: dict[str, Any]) -> dict[str, Any]:
    """Tira campos vazios para o JSON caber melhor no contexto da rotina."""
    return {chave: valor for chave, valor in item.items() if valor not in (None, "", [], {})}


def ler(horas: float, agora: datetime | None = None) -> list[dict[str, Any]]:
    desde = (agora or datetime.now(UTC)) - timedelta(hours=horas)
    itens = chamar("rotina_itens", {"desde": desde.isoformat()})
    return [compactar(item) for item in itens or []]


def hoje_brasilia(agora: datetime | None = None) -> date:
    return (agora or datetime.now(UTC)).astimezone(BRASILIA).date()


def validar_edicao(tipo: str, titulo: str, conteudo: str) -> tuple[str, str]:
    if tipo not in TIPOS:
        raise ErroRotina(f"tipo deve ser {' ou '.join(TIPOS)}")
    titulo, conteudo = titulo.strip(), conteudo.strip()
    if not titulo or len(titulo) > LIMITE_TITULO:
        raise ErroRotina(f"título vazio ou com mais de {LIMITE_TITULO} caracteres")
    if not conteudo or len(conteudo) > LIMITE_CONTEUDO:
        raise ErroRotina(f"conteúdo vazio ou com mais de {LIMITE_CONTEUDO} caracteres")
    return titulo, conteudo


def publicar(tipo: str, titulo: str, conteudo: str, referencia: date) -> int:
    titulo, conteudo = validar_edicao(tipo, titulo, conteudo)
    corpo = {
        "tipo": tipo,
        "referencia": referencia.isoformat(),
        "titulo": titulo,
        "conteudo": conteudo,
    }
    return int(chamar("rotina_publicar", corpo))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("gerar-token", help="gera o token da rotina e o SQL para cadastrá-lo")
    p_ler = sub.add_parser("ler", help="imprime em JSON os itens triados das últimas horas")
    p_ler.add_argument("--horas", type=float, default=30)
    p_pub = sub.add_parser("publicar", help="grava a edição (markdown) que o portal mostra")
    p_pub.add_argument("tipo", choices=TIPOS)
    p_pub.add_argument("arquivo", help="arquivo .md com o conteúdo")
    p_pub.add_argument("--titulo", required=True)
    p_pub.add_argument("--referencia", type=date.fromisoformat, help="AAAA-MM-DD (padrão: hoje)")
    args = parser.parse_args(argv)
    # JSON e mensagens sempre em UTF-8, mesmo no console do Windows (cp1252).
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")

    try:
        if args.comando == "gerar-token":
            token, hash_ = gerar_token()
            print("Token (guarde como ROTINA_TOKEN no ambiente da rotina; não commite):")
            print(f"  {token}")
            print("\nSQL para o Supabase (só o hash vai para o banco):")
            print(f"  insert into public.rotina_acesso (hash) values ('{hash_}');")
        elif args.comando == "ler":
            json.dump(ler(args.horas), sys.stdout, ensure_ascii=False, indent=1)
            print()
        else:
            with open(args.arquivo, encoding="utf-8") as arquivo:
                conteudo = arquivo.read()
            referencia = args.referencia or hoje_brasilia()
            novo_id = publicar(args.tipo, args.titulo, conteudo, referencia)
            print(f"edição {args.tipo} de {referencia} publicada (id {novo_id})")
    except ErroRotina as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
