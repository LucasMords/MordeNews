"""Carrega configuração a partir de variáveis de ambiente (.env) e dos arquivos YAML em config/."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from radar.modelos import Fonte

RAIZ = Path(__file__).resolve().parents[2]
PASTA_CONFIG = RAIZ / "config"
ARQUIVO_FONTES = PASTA_CONFIG / "fontes.yaml"
ARQUIVO_PERFIL = PASTA_CONFIG / "perfil.md"
NOME_ROBO = "RadarPessoal"


class ErroConfiguracao(RuntimeError):
    """Variável de ambiente obrigatória ausente ou inválida."""


@dataclass(frozen=True)
class Configuracao:
    supabase_url: str | None
    supabase_service_role_key: str | None
    gemini_api_key: str | None
    gemini_model: str
    nota_minima_resumo: int
    contato: str | None = None
    email_remetente: str | None = None
    email_senha_app: str | None = None
    email_destino: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_porta: int = 465
    resumo_maximo: int = 30
    github_token: str | None = None
    nota_minima_estagios: int = 0  # vagas aparecem mesmo com nota baixa (pedido do usuário)
    estagios_maximo: int = 15  # limite próprio, para as vagas não disputarem espaço com notícias
    nota_minima_concursos: int = 0  # concursos não são filtrados por nota (pedido do usuário)
    concursos_maximo: int = 20

    def __repr__(self) -> str:  # nunca expor chaves nem dados pessoais em logs ou tracebacks
        return (
            f"Configuracao(supabase_url={self.supabase_url!r}, gemini_model={self.gemini_model!r}, "
            f"nota_minima_resumo={self.nota_minima_resumo}, segredos=<ocultos>)"
        )

    @property
    def user_agent(self) -> str:
        """User-Agent dos coletores. O contato vem do ambiente para não ficar no repositório."""
        return f"{NOME_ROBO}/0.1 (+{self.contato})" if self.contato else f"{NOME_ROBO}/0.1"

    def exigir_supabase(self) -> tuple[str, str]:
        """Devolve (url, chave) ou falha com mensagem clara se faltar algo."""
        url = _exigir("SUPABASE_URL", self.supabase_url)
        chave = _exigir("SUPABASE_SERVICE_ROLE_KEY", self.supabase_service_role_key)
        return url.rstrip("/"), chave

    def exigir_gemini(self) -> str:
        return _exigir("GEMINI_API_KEY", self.gemini_api_key)

    def exigir_email(self) -> tuple[str, str, str]:
        """Devolve (remetente, senha_app, destino). Espaços da senha de app são removidos."""
        remetente = _exigir("EMAIL_REMETENTE", self.email_remetente)
        senha = _exigir("EMAIL_SENHA_APP", self.email_senha_app).replace(" ", "")
        destino = _exigir("EMAIL_DESTINO", self.email_destino)
        return remetente, senha, destino


def _exigir(nome: str, valor: str | None) -> str:
    if not valor:
        raise ErroConfiguracao(
            f"Variável de ambiente {nome} não definida. Preencha o .env (veja .env.example)."
        )
    return valor


def _texto(nome: str) -> str | None:
    valor = os.environ.get(nome, "").strip()
    return valor or None


def _inteiro(nome: str, padrao: int) -> int:
    bruto = _texto(nome)
    if bruto is None:
        return padrao
    try:
        return int(bruto)
    except ValueError as erro:
        raise ErroConfiguracao(f"{nome} deve ser um número inteiro, recebido {bruto!r}.") from erro


def ler_ambiente() -> Configuracao:
    """Lê as variáveis do ambiente atual, sem cache (útil em testes)."""
    return Configuracao(
        supabase_url=_texto("SUPABASE_URL"),
        supabase_service_role_key=_texto("SUPABASE_SERVICE_ROLE_KEY"),
        gemini_api_key=_texto("GEMINI_API_KEY"),
        gemini_model=_texto("GEMINI_MODEL") or "gemini-3.5-flash-lite",
        nota_minima_resumo=_inteiro("NOTA_MINIMA_RESUMO", 6),
        contato=_texto("RADAR_CONTATO"),
        email_remetente=_texto("EMAIL_REMETENTE"),
        email_senha_app=_texto("EMAIL_SENHA_APP"),
        email_destino=_texto("EMAIL_DESTINO"),
        smtp_host=_texto("SMTP_HOST") or "smtp.gmail.com",
        smtp_porta=_inteiro("SMTP_PORTA", 465),
        resumo_maximo=_inteiro("RESUMO_MAXIMO", 30),
        github_token=_texto("GITHUB_TOKEN"),
        nota_minima_estagios=_inteiro("NOTA_MINIMA_ESTAGIOS", 0),
        estagios_maximo=_inteiro("ESTAGIOS_MAXIMO", 15),
        nota_minima_concursos=_inteiro("NOTA_MINIMA_CONCURSOS", 0),
        concursos_maximo=_inteiro("CONCURSOS_MAXIMO", 20),
    )


@lru_cache(maxsize=1)
def carregar() -> Configuracao:
    """Carrega o .env da raiz do projeto (se existir) e devolve a configuração.

    Variáveis já definidas no ambiente (ex.: GitHub Secrets) têm prioridade sobre o .env.
    """
    load_dotenv(RAIZ / ".env", override=False)
    return ler_ambiente()


def carregar_perfil(caminho: Path = ARQUIVO_PERFIL) -> str:
    """Texto do perfil de interesses usado pela triagem."""
    dica = "Copie config/perfil.exemplo.md para config/perfil.md (no GitHub: secret PERFIL_MD)."
    if not caminho.exists():
        raise ErroConfiguracao(f"Perfil não encontrado: {caminho}. {dica}")
    texto = caminho.read_text(encoding="utf-8").strip()
    if not texto:
        raise ErroConfiguracao(f"Perfil vazio: {caminho}. {dica}")
    return texto


def carregar_fontes_validas(caminho: Path = ARQUIVO_FONTES) -> list[Fonte]:
    """Lê o fontes.yaml e valida cada fonte. Erro de configuração falha logo, com mensagem clara."""
    fontes: list[Fonte] = []
    for modulo, lista in carregar_fontes(caminho).items():
        for posicao, bruta in enumerate(lista, start=1):
            if not isinstance(bruta, dict):
                raise ErroConfiguracao(
                    f"{caminho.name}: {modulo} #{posicao} deve ser um mapeamento."
                )
            try:
                fontes.append(Fonte.model_validate({**bruta, "modulo": modulo}))
            except ValidationError as erro:
                nome = bruta.get("nome", f"#{posicao}")
                raise ErroConfiguracao(
                    f"{caminho.name}: fonte {modulo}/{nome} inválida: {erro}"
                ) from erro
    nomes = [f.nome for f in fontes]
    repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
    if repetidos:
        raise ErroConfiguracao(f"{caminho.name}: nomes de fonte repetidos: {', '.join(repetidos)}")
    return fontes


def carregar_fontes(caminho: Path = ARQUIVO_FONTES) -> dict[str, list[dict[str, Any]]]:
    """Lê o fontes.yaml e devolve {modulo: [fonte, ...]}. Módulos vazios viram lista vazia."""
    if not caminho.exists():
        raise ErroConfiguracao(f"Arquivo de fontes não encontrado: {caminho}")
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    if not isinstance(dados, dict):
        raise ErroConfiguracao(f"{caminho.name} deve ser um mapeamento modulo -> lista de fontes.")
    fontes: dict[str, list[dict[str, Any]]] = {}
    for modulo, lista in dados.items():
        if lista is None:
            lista = []
        if not isinstance(lista, list):
            raise ErroConfiguracao(f"Em {caminho.name}, '{modulo}' deve ser uma lista de fontes.")
        fontes[str(modulo)] = lista
    return fontes
